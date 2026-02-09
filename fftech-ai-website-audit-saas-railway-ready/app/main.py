# -*- coding: utf-8 -*-
"""
app/main.py

Fully integrated FastAPI app for:
- GET /                  -> serves app/templates/index.html
- GET /health            -> health check
- WS  /ws                -> runs audit + streams progress + sends final result (runner_result)
- POST /api/audit/run    -> REST audit fallback (returns runner_result)
- POST /api/audit/pdf    -> generates PDF (returns PDF bytes)

Compatible with runner.py output:
    {
      audited_url, overall_score, grade, breakdown, chart_data, dynamic, (optional error)
    }

WebSocket message contract (matches your updated UI):
    { status: str, progress: int, payload: any|null }
    final:
    { status: "completed", progress: 100, result: runner_result }
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import runner + PDF helper
from app.audit.runner import WebsiteAuditRunner, generate_pdf_from_runner_result


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI(title="Website Audit Pro", version="2.1.0")

# If you don't need CORS, you can remove this
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent  # .../app
INDEX_HTML_PATH = BASE_DIR / "templates" / "index.html"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _safe_filename(name: str, default: str = "audit_report") -> str:
    name = (name or "").strip()
    if not name:
        name = default
    name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name).strip("._-") or default
    return name[:90]


async def _ws_send(ws: WebSocket, message: Dict[str, Any]) -> None:
    """
    Safe WebSocket send. Never break the audit if the client disconnects.
    """
    try:
        await ws.send_text(json.dumps(message, ensure_ascii=False))
    except Exception:
        # client disconnected or network issue
        pass


def _runner_error_message(result: Dict[str, Any]) -> Optional[str]:
    """
    Runner fail shape uses 'error'. If present, treat as failure.
    """
    err = result.get("error")
    if err:
        return str(err)
    return None


# -----------------------------------------------------------------------------
# Pydantic Models
# -----------------------------------------------------------------------------
class AuditRunRequest(BaseModel):
    url: str = Field(..., description="Website URL (domain or full URL)")


class PdfRequest(BaseModel):
    url: str = Field(..., description="Website URL to audit")
    client_name: Optional[str] = ""
    brand_name: Optional[str] = ""
    report_title: Optional[str] = ""
    website_name: Optional[str] = ""
    logo_path: Optional[str] = ""


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
async def index(_: Request) -> HTMLResponse:
    if not INDEX_HTML_PATH.exists():
        return HTMLResponse(
            f"<h3>index.html not found</h3><p>Expected: {INDEX_HTML_PATH}</p>",
            status_code=500,
        )
    return HTMLResponse(INDEX_HTML_PATH.read_text(encoding="utf-8"))


# -----------------------------------------------------------------------------
# WebSocket: /ws
# - Client sends: {"url":"..."}
# - Server streams progress: {"status": "...", "progress": n, "payload": {...|None}}
# - Final: {"status":"completed","progress":100,"result": runner_result}
# -----------------------------------------------------------------------------
@app.websocket("/ws")
async def ws_audit(ws: WebSocket):
    await ws.accept()

    runner = WebsiteAuditRunner()

    try:
        while True:
            raw = await ws.receive_text()

            # Expect JSON: {"url": "..."}
            try:
                msg = json.loads(raw)
            except Exception:
                await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": "Invalid JSON"}})
                continue

            url = (msg.get("url") or "").strip()
            if not url:
                await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": "URL is required"}})
                continue

            # Progress callback -> stream to WS
            async def progress_cb(status: str, percent: int, payload: Optional[dict] = None):
                # runner sends payload=None for some stages; that's okay
                await _ws_send(ws, {"status": status, "progress": int(percent), "payload": payload})

            # Run the audit
            try:
                result = await runner.run(url, progress_cb=progress_cb)

                # If runner returned an error shape, still send it clearly
                err = _runner_error_message(result)
                if err:
                    await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": err, "result": result}})
                    continue

                # Final message for UI
                await _ws_send(ws, {"status": "completed", "progress": 100, "result": result})

            except Exception as e:
                await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": str(e)}})

    except WebSocketDisconnect:
        return
    except Exception:
        return


# -----------------------------------------------------------------------------
# REST fallback: /api/audit/run
# Returns runner_result directly (same shape as runner output)
# -----------------------------------------------------------------------------
@app.post("/api/audit/run")
async def api_audit_run(req: AuditRunRequest) -> JSONResponse:
    runner = WebsiteAuditRunner()
    result = await runner.run(req.url, progress_cb=None)
    return JSONResponse(result)


# -----------------------------------------------------------------------------
# PDF: /api/audit/pdf
# - Runs audit (or you can cache and reuse later)
# - Generates PDF using generate_pdf_from_runner_result()
# - Returns PDF bytes
# -----------------------------------------------------------------------------
@app.post("/api/audit/pdf")
async def api_audit_pdf(req: PdfRequest):
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    runner = WebsiteAuditRunner()

    # 1) Run audit
    try:
        runner_result = await runner.run(url, progress_cb=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {e}")

    # if runner error
    err = _runner_error_message(runner_result)
    if err:
        raise HTTPException(status_code=400, detail=f"Audit error: {err}")

    # 2) Prepare metadata
    report_title = (req.report_title or "").strip() or "Website Audit Report"
    client_name = (req.client_name or "").strip() or "N/A"
    brand_name = (req.brand_name or "").strip() or "FF Tech"
    website_name = (req.website_name or "").strip() or ""
    logo_path = (req.logo_path or "").strip() or None

    # 3) Output PDF to a temp file
    tmp_dir = Path(tempfile.mkdtemp(prefix="audit_pdf_"))
    fname = _safe_filename(website_name or runner_result.get("audited_url") or "audit_report")
    pdf_path = tmp_dir / f"{fname}.pdf"

    try:
        generate_pdf_from_runner_result(
            runner_result=runner_result,
            output_path=str(pdf_path),
            logo_path=logo_path,
            report_title=report_title,
            client_name=client_name,
            brand_name=brand_name,
            website_name=website_name or None,
            audit_date=None,
        )
    except RuntimeError as e:
        # Common: reportlab missing
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    if not pdf_path.exists():
        raise HTTPException(status_code=500, detail="PDF generation failed (file not created)")

    # 4) Return PDF file
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
        headers={"Content-Disposition": f'attachment; filename=\"{pdf_path.name}\"'},
    )


# -----------------------------------------------------------------------------
# Local run (optional)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
