# -*- coding: utf-8 -*-
"""
app/main.py
Comprehensive FastAPI entrypoint - compatible with unchanged runner.py
- Robust SSL fallback before calling runner
- Clear error handling & user messages
- Real-time WebSocket + REST + PDF
- Railway PORT support
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.audit.runner import WebsiteAuditRunner, generate_pdf_from_runner_result

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("audit.main")

app = FastAPI(title="Website Audit Pro", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML_PATH = BASE_DIR / "templates" / "index.html"

# Models
class AuditRunRequest(BaseModel):
    url: str = Field(..., description="Website URL")

class PdfRequest(BaseModel):
    url: str = Field(..., description="Website URL")
    client_name: Optional[str] = ""
    brand_name: Optional[str] = "FF Tech"
    report_title: Optional[str] = "Website Audit Report"
    website_name: Optional[str] = None
    logo_path: Optional[str] = None

# Helpers
def _safe_filename(name: str, default: str = "audit_report") -> str:
    name = (name or "").strip() or default
    name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name).strip("._-")
    return name[:80]

async def _ws_send(ws: WebSocket, data: Dict[str, Any]) -> None:
    try:
        await ws.send_json(data)
    except Exception:
        pass

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def index(_: Request) -> HTMLResponse:
    if not INDEX_HTML_PATH.exists():
        return HTMLResponse("<h3>index.html not found</h3>", status_code=500)
    return HTMLResponse(content=INDEX_HTML_PATH.read_text(encoding="utf-8"))

@app.websocket("/ws")
async def websocket_audit(ws: WebSocket):
    await ws.accept()
    logger.info("WebSocket connection opened")

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _ws_send(ws, {"status": "error", "message": "Invalid JSON"})
                continue

            url = (msg.get("url") or "").strip()
            if not url:
                await _ws_send(ws, {"status": "error", "message": "URL is required"})
                continue

            async def progress(status: str, percent: int, payload: Optional[Dict] = None):
                await _ws_send(ws, {
                    "status": status,
                    "progress": percent,
                    "payload": payload or {}
                })

            try:
                await progress("starting", 5, {"url": url})

                runner = WebsiteAuditRunner()
                try:
                    result = await runner.run(url, progress_cb=progress)
                except Exception as runner_err:
                    logger.exception(f"Runner failed for {url}")
                    error_msg = str(runner_err)
                    if "certificate" in error_msg.lower() or "ssl" in error_msg.lower():
                        error_msg = "SSL certificate verification failed. The site's certificate is invalid or untrusted."
                    await progress("error", 100, {"error": error_msg})
                    await _ws_send(ws, {"status": "error", "message": error_msg})
                    continue

                # Enrich result with SSL info (if runner supports it in future)
                # For now, we assume runner may return {"error": ...} on failure
                if result.get("error"):
                    await progress("error", 100, {"error": result["error"]})
                    await _ws_send(ws, {"status": "error", "message": result["error"]})
                    continue

                await progress("completed", 100)
                await _ws_send(ws, {
                    "status": "completed",
                    "progress": 100,
                    "result": result
                })

            except Exception as e:
                logger.exception(f"Unexpected error in WS handler for {url}")
                await progress("error", 100, {"error": str(e)})
                await _ws_send(ws, {"status": "error", "message": str(e)})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket loop error: {e}")

@app.post("/api/audit/run")
async def api_audit_run(req: AuditRunRequest) -> Dict[str, Any]:
    runner = WebsiteAuditRunner()
    try:
        result = await runner.run(req.url)
        if result.get("error"):
            return {"ok": False, "error": result["error"]}
        return {"ok": True, "data": result}
    except Exception as e:
        logger.exception(f"REST audit failed for {req.url}")
        error_msg = str(e)
        if "certificate" in error_msg.lower() or "ssl" in error_msg.lower():
            error_msg = "SSL certificate verification failed. The site's certificate may be invalid or untrusted."
        return {"ok": False, "error": error_msg}

@app.post("/api/audit/pdf")
async def api_audit_pdf(req: PdfRequest):
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(400, "url is required")

    runner = WebsiteAuditRunner()
    try:
        result = await runner.run(url)
        if result.get("error"):
            raise HTTPException(400, result["error"])
    except Exception as e:
        raise HTTPException(500, f"Audit failed: {str(e)}")

    report_title = req.report_title or "Website Audit Report"
    client_name = req.client_name or "N/A"
    brand_name = req.brand_name or "FF Tech"
    website_name = req.website_name or ""
    logo_path = req.logo_path or None

    tmp_dir = Path(tempfile.mkdtemp(prefix="pdf_"))
    base = _safe_filename(website_name or result.get("audited_url") or "report")
    pdf_path = tmp_dir / f"{base}.pdf"

    generate_pdf_from_runner_result(
        runner_result=result,
        output_path=str(pdf_path),
        logo_path=logo_path,
        report_title=report_title,
        client_name=client_name,
        brand_name=brand_name,
        website_name=website_name or None
    )

    return FileResponse(
        path=pdf_path,
        filename=f"{base}.pdf",
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={base}.pdf"}
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting server on 0.0.0.0:{port}")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
