# -*- coding: utf-8 -*-
"""
main.py

FastAPI entrypoint for:
- GET /                -> serves index.html (Bootstrap + Chart.js UI)
- WS  /ws              -> streams audit progress + final results
- POST /api/audit/pdf  -> generates and downloads professional PDF report

Works with:
- app/audit/runner.py (WebsiteAuditRunner + PDF helper functions)
- app/audit/pdf_report.py (reportlab-based PDF generator)
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.audit.runner import WebsiteAuditRunner, generate_pdf_from_runner_result


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI(title="Website Audit Pro", version="2.0")

# Optional CORS (handy if UI hosted elsewhere; safe for Railway)
# You can lock this down later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Paths: adjust if your templates folder differs
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
INDEX_HTML_PATH = TEMPLATES_DIR / "index.html"


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------
def _safe_filename(name: str, default: str = "audit_report") -> str:
    """
    Make a safe filename (no slashes, weird chars).
    """
    name = (name or "").strip()
    if not name:
        name = default
    name = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", name)
    name = name.strip("._-") or default
    return name[:80]


async def _ws_send_json(ws: WebSocket, payload: Dict[str, Any]) -> None:
    """
    Never let send exceptions crash server logic.
    """
    try:
        await ws.send_text(json.dumps(payload, ensure_ascii=False))
    except Exception:
        # Client likely disconnected
        pass


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class PdfRequest(BaseModel):
    url: str = Field(..., description="Website URL to audit")
    client_name: Optional[str] = ""
    brand_name: Optional[str] = ""
    report_title: Optional[str] = ""
    website_name: Optional[str] = ""
    logo_path: Optional[str] = ""  # optional path on server filesystem


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """
    Serve your index.html UI.
    """
    if not INDEX_HTML_PATH.exists():
        return HTMLResponse(
            content=f"<h3>index.html not found</h3><p>Expected at: {INDEX_HTML_PATH}</p>",
            status_code=404,
        )
    return HTMLResponse(INDEX_HTML_PATH.read_text(encoding="utf-8"))


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"ok": True}


# -----------------------------------------------------------------------------
# WebSocket: /ws
# UI contract (from your index.html):
# - client sends: {"url": "..."}
# - server sends progress: {"status": "...", "progress": 0-100, "payload": {...}}
# - final: {"status":"completed","progress":100,"result":{runner_result}}
# -----------------------------------------------------------------------------
@app.websocket("/ws")
async def ws_audit(ws: WebSocket):
    await ws.accept()

    runner = WebsiteAuditRunner()

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                await _ws_send_json(ws, {"status": "error", "progress": 100, "error": "Invalid JSON"})
                continue

            url = (msg.get("url") or "").strip()
            if not url:
                await _ws_send_json(ws, {"status": "error", "progress": 100, "error": "URL is required"})
                continue

            # Progress callback that streams to WebSocket
            async def progress_cb(status: str, percent: int, payload: Optional[dict] = None):
                await _ws_send_json(ws, {"status": status, "progress": int(percent), "payload": payload})

            # Run audit
            try:
                result = await runner.run(url, progress_cb=progress_cb)

                # Send a final "completed" frame with result (UI expects it)
                await _ws_send_json(ws, {"status": "completed", "progress": 100, "result": result})
            except Exception as e:
                await _ws_send_json(ws, {"status": "error", "progress": 100, "error": str(e)})

    except WebSocketDisconnect:
        # client closed tab
        return
    except Exception:
        # unexpected
        return


# -----------------------------------------------------------------------------
# REST: Optional quick audit endpoint (handy for testing / fallback)
# -----------------------------------------------------------------------------
@app.post("/api/audit/run")
async def api_audit_run(payload: Dict[str, Any]) -> JSONResponse:
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    runner = WebsiteAuditRunner()
    result = await runner.run(url, progress_cb=None)
    return JSONResponse(result)


# -----------------------------------------------------------------------------
# REST: PDF generation endpoint used by your index.html button
# POST /api/audit/pdf -> returns application/pdf bytes
# -----------------------------------------------------------------------------
@app.post("/api/audit/pdf")
async def api_audit_pdf(req: PdfRequest):
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    runner = WebsiteAuditRunner()

    # 1) Run audit (no progress needed for PDF)
    try:
        runner_result = await runner.run(url, progress_cb=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {e}")

    # If runner returned stable failure shape with "error"
    if runner_result.get("error"):
        raise HTTPException(status_code=400, detail=f"Audit error: {runner_result['error']}")

    # 2) Generate PDF to a temp file
    report_title = (req.report_title or "").strip()
    client_name = (req.client_name or "").strip()
    brand_name = (req.brand_name or "").strip()
    website_name = (req.website_name or "").strip()
    logo_path = (req.logo_path or "").strip() or None

    # Use a temp directory for safe file creation
    tmp_dir = Path(tempfile.mkdtemp(prefix="audit_pdf_"))
    filename_base = _safe_filename(website_name or runner_result.get("audited_url") or "audit_report")
    pdf_path = tmp_dir / f"{filename_base}.pdf"

    try:
        generate_pdf_from_runner_result(
            runner_result=runner_result,
            output_path=str(pdf_path),
            logo_path=logo_path,
            report_title=report_title or "Website Audit Report",
            client_name=client_name or "N/A",
            brand_name=brand_name or "FF Tech",
            website_name=website_name or None,
            audit_date=None,
        )
    except RuntimeError as e:
        # Common cause: reportlab not installed
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    if not pdf_path.exists():
        raise HTTPException(status_code=500, detail="PDF generation failed (file not created)")

    # 3) Return PDF file
    # Note: FileResponse will stream from disk efficiently.
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
        headers={
            # Extra safety for downloads
            "Content-Disposition": f'attachment; filename="{pdf_path.name}"'
        },
    )
