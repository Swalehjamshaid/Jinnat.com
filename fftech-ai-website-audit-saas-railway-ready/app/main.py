# -*- coding: utf-8 -*-
"""
app/main.py
Fully integrated FastAPI entrypoint with improved SSL handling
"""
from __future__ import annotations
import asyncio
import json
import os
import re
import tempfile
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.audit.runner import WebsiteAuditRunner, generate_pdf_from_runner_result

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit")

app = FastAPI(title="Website Audit Pro", version="2.0.0")

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

# Helpers
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

# Models
class AuditRunRequest(BaseModel):
    url: str = Field(..., description="Website URL (domain or full URL)")

class PdfRequest(BaseModel):
    url: str = Field(..., description="Website URL to audit")
    client_name: Optional[str] = ""
    brand_name: Optional[str] = ""
    report_title: Optional[str] = ""
    website_name: Optional[str] = ""
    logo_path: Optional[str] = ""

# Improved fetch function with robust SSL fallback
async def fetch_url(url: str, timeout: float = 25.0) -> Dict[str, Any]:
    headers = {"User-Agent": "FFTechAuditBot/2.0 (+https://yourdomain.com)"}
    url = url if url.startswith(("http://", "https://")) else f"https://{url}"

    # Try strict verification
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=True) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            return {
                "ok": True,
                "html": r.text,
                "final_url": str(r.url),
                "ssl_relaxed": False,
                "error": None
            }
    except httpx.SSLError as ssl_err:
        logger.warning(f"SSL verification failed for {url}: {ssl_err} → retrying without verification")
    except Exception as e:
        logger.error(f"Fetch failed for {url}: {e}")
        return {"ok": False, "html": "", "final_url": url, "ssl_relaxed": False, "error": str(e)}

    # Fallback: no verification
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            return {
                "ok": True,
                "html": r.text,
                "final_url": str(r.url),
                "ssl_relaxed": True,
                "error": None
            }
    except Exception as e:
        logger.error(f"Fetch failed even without SSL verification for {url}: {e}")
        return {"ok": False, "html": "", "final_url": url, "ssl_relaxed": False, "error": str(e)}

# Routes
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

            async def progress_cb(status: str, percent: int, payload: Optional[dict] = None):
                await _ws_send(ws, {"status": status, "progress": int(percent), "payload": payload})

            try:
                # Fetch HTML with robust SSL handling
                fetch_result = await fetch_url(url)
                if not fetch_result["ok"]:
                    await progress_cb("error", 100, {"error": fetch_result["error"]})
                    await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": fetch_result["error"]}})
                    continue

                # Pass HTML to runner
                runner = WebsiteAuditRunner()
                result = await runner.run(url, progress_cb=progress_cb)

                # Add SSL info to result for frontend warning
                result["ssl_relaxed"] = fetch_result["ssl_relaxed"]

                await _ws_send(ws, {"status": "completed", "progress": 100, "result": result})
            except Exception as e:
                logger.exception(f"Audit error for {url}")
                await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": str(e)}})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass

@app.post("/api/audit/run")
async def api_audit_run(req: AuditRunRequest) -> JSONResponse:
    fetch_result = await fetch_url(req.url)
    if not fetch_result["ok"]:
        return JSONResponse({"ok": False, "error": fetch_result["error"]}, status_code=400)

    runner = WebsiteAuditRunner()
    result = await runner.run(req.url)
    result["ssl_relaxed"] = fetch_result["ssl_relaxed"]
    return JSONResponse({"ok": True, "data": result})

@app.post("/api/audit/pdf")
async def api_audit_pdf(req: PdfRequest):
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    fetch_result = await fetch_url(url)
    if not fetch_result["ok"]:
        raise HTTPException(status_code=400, detail=fetch_result["error"])

    runner = WebsiteAuditRunner()
    try:
        runner_result = await runner.run(url)
        runner_result["ssl_relaxed"] = fetch_result["ssl_relaxed"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {e}")

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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
