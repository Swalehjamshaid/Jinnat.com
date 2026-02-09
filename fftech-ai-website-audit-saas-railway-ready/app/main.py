# -*- coding: utf-8 -*-
"""
app/main.py
Fully integrated FastAPI entrypoint for Website Audit Pro
- Handles SSL failures from runner.py gracefully
- Sends clear error messages to frontend
- Real-time WebSocket progress + results
- REST endpoints for audit & PDF
- Compatible with unchanged runner.py
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

from app.audit.runner import WebsiteAuditRunner, generate_pdf_from_runner_result

app = FastAPI(title="Website Audit Pro", version="2.0.0")

# Enable CORS (optional, but useful for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML_PATH = BASE_DIR / "templates" / "index.html"

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _safe_filename(name: str, default: str = "audit_report") -> str:
    name = (name or "").strip()
    if not name:
        name = default
    name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name).strip("._-") or default
    return name[:80]

async def _ws_send(ws: WebSocket, data: Dict[str, Any]) -> None:
    try:
        await ws.send_text(json.dumps(data, ensure_ascii=False))
    except Exception:
        pass

# -----------------------------------------------------------------------------
# Models
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
# WebSocket: /ws - UPDATED with proper error handling
# -----------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_audit(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": "Invalid JSON"}})
                continue

            url = (msg.get("url") or "").strip()
            if not url:
                await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": "URL is required"}})
                continue

            # Progress callback
            async def progress_cb(status: str, percent: int, payload: Optional[dict] = None):
                await _ws_send(ws, {"status": status, "progress": int(percent), "payload": payload})

            try:
                await progress_cb("starting", 5, {"url": url})

                runner = WebsiteAuditRunner()
                result = await runner.run(url, progress_cb=progress_cb)

                # Handle runner returning explicit error
                if result.get("error"):
                    error_msg = result["error"]
                    if "CERTIFICATE_VERIFY_FAILED" in error_msg or "certificate" in error_msg.lower():
                        error_msg = "SSL certificate verification failed. The website has an invalid or untrusted certificate."
                    elif "timeout" in error_msg.lower():
                        error_msg = "Request timed out. The site may be slow or blocking the tool."
                    await progress_cb("error", 100, {"error": error_msg})
                    await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": error_msg}})
                    continue

                # Success
                await progress_cb("completed", 100)
                await _ws_send(ws, {"status": "completed", "progress": 100, "result": result})

            except Exception as e:
                error_msg = str(e)
                if "CERTIFICATE_VERIFY_FAILED" in error_msg or "certificate" in error_msg.lower():
                    error_msg = "SSL certificate verification failed. The website has an invalid or untrusted certificate."
                elif "timeout" in error_msg.lower():
                    error_msg = "Request timed out. The site may be slow or blocking the tool."
                else:
                    error_msg = f"Audit failed: {error_msg}"

                await progress_cb("error", 100, {"error": error_msg})
                await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": error_msg}})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        pass  # Avoid crashing the server

# -----------------------------------------------------------------------------
# REST: /api/audit/run (optional fallback)
# -----------------------------------------------------------------------------
@app.post("/api/audit/run")
async def api_audit_run(req: AuditRunRequest) -> JSONResponse:
    runner = WebsiteAuditRunner()
    result = await runner.run(req.url, progress_cb=None)
    return JSONResponse(result)

# -----------------------------------------------------------------------------
# REST: /api/audit/pdf (PDF Download)
# -----------------------------------------------------------------------------
@app.post("/api/audit/pdf")
async def api_audit_pdf(req: PdfRequest):
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    runner = WebsiteAuditRunner()
    try:
        runner_result = await runner.run(url, progress_cb=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")

    if runner_result.get("error"):
        raise HTTPException(status_code=400, detail=f"Audit error: {runner_result['error']}")

    report_title = (req.report_title or "").strip() or "Website Audit Report"
    client_name = (req.client_name or "").strip() or "N/A"
    brand_name = (req.brand_name or "").strip() or "FF Tech"
    website_name = (req.website_name or "").strip() or ""
    logo_path = (req.logo_path or "").strip() or None

    tmp_dir = Path(tempfile.mkdtemp(prefix="audit_pdf_"))
    base = _safe_filename(website_name or runner_result.get("audited_url") or "audit_report")
    pdf_path = tmp_dir / f"{base}.pdf"

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
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    if not pdf_path.exists():
        raise HTTPException(status_code=500, detail="PDF file not created")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
        headers={"Content-Disposition": f'attachment; filename="{pdf_path.name}"'},
    )

# -----------------------------------------------------------------------------
# Local run entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
