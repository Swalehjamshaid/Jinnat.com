# -*- coding: utf-8 -*-
"""
app/main.py
Comprehensive FastAPI entrypoint for Website Audit Pro
- Serves frontend (index.html)
- WebSocket /ws for real-time audit progress and results
- REST /api/audit/run for audit
- REST /api/audit/pdf for PDF download
- Robust SSL certificate handling with fallback
- Compatible with app/audit/runner.py
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

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("audit.app")

# FastAPI app
app = FastAPI(
    title="Website Audit Pro",
    description="Professional website auditing tool with real-time progress, scoring and PDF reports",
    version="2.0.0",
    docs_url="/docs",
    redoc_url=None,
)

# Enable CORS (useful for frontend development or external calls)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML_PATH = BASE_DIR / "templates" / "index.html"

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class AuditRunRequest(BaseModel):
    url: str = Field(..., description="Website URL (domain or full URL)")

class PdfRequest(BaseModel):
    url: str = Field(..., description="Website URL to audit")
    client_name: Optional[str] = Field(default="", description="Client name for PDF")
    brand_name: Optional[str] = Field(default="FF Tech", description="Brand name for PDF")
    report_title: Optional[str] = Field(default="Website Audit Report", description="Report title")
    website_name: Optional[str] = Field(default=None, description="Website name")
    logo_path: Optional[str] = Field(default=None, description="Path to logo image")

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
    """Safe WebSocket send - never crash on disconnect"""
    try:
        await ws.send_json(data)
    except Exception:
        pass

# -----------------------------------------------------------------------------
# Robust Fetch with SSL Fallback
# -----------------------------------------------------------------------------
async def fetch_url(url: str, timeout: float = 25.0) -> Dict[str, Any]:
    """
    Fetch URL content with automatic SSL fallback on verification failure.
    Returns structured result with ssl_relaxed flag.
    """
    headers = {"User-Agent": "FFTechAuditBot/2.0 (audit; +https://yourdomain.com)"}
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    # Step 1: Try with full SSL verification
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=True
        ) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return {
                "ok": True,
                "html": resp.text,
                "final_url": str(resp.url),
                "ssl_relaxed": False,
                "error": None
            }
    except httpx.ConnectError as e:
        error_str = str(e).lower()
        if "certificate" in error_str or "ssl" in error_str or "tls" in error_str:
            logger.warning(f"SSL verification failed for {url}: {e} → retrying without verification")
        else:
            logger.error(f"Connection failed for {url}: {e}")
            return {"ok": False, "html": "", "final_url": url, "ssl_relaxed": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected fetch error for {url}: {e}")
        return {"ok": False, "html": "", "final_url": url, "ssl_relaxed": False, "error": str(e)}

    # Step 2: Fallback - disable SSL verification
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=False
        ) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return {
                "ok": True,
                "html": resp.text,
                "final_url": str(resp.url),
                "ssl_relaxed": True,
                "error": None
            }
    except Exception as e:
        logger.error(f"Fetch failed even without verification for {url}: {e}")
        return {"ok": False, "html": "", "final_url": url, "ssl_relaxed": False, "error": str(e)}

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/health")
async def health() -> Dict[str, Any]:
    """Simple health check endpoint"""
    return {"status": "healthy", "service": "website-audit-pro"}

@app.get("/", response_class=HTMLResponse)
async def serve_frontend(_: Request) -> HTMLResponse:
    """Serve the main frontend (index.html)"""
    if not INDEX_HTML_PATH.exists():
        logger.error(f"Frontend template not found: {INDEX_HTML_PATH}")
        return HTMLResponse(
            content="<h3>index.html not found</h3><p>Check templates/ directory</p>",
            status_code=500
        )
    return HTMLResponse(content=INDEX_HTML_PATH.read_text(encoding="utf-8"))

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Real-time audit via WebSocket"""
    await ws.accept()
    logger.info("WebSocket connection opened")

    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await _ws_send(ws, {"status": "error", "message": "Invalid JSON"})
                continue

            url = (msg.get("url") or "").strip()
            if not url:
                await _ws_send(ws, {"status": "error", "message": "URL is required"})
                continue

            # Progress callback
            async def progress(status: str, percent: int, payload: Optional[Dict] = None):
                await _ws_send(ws, {
                    "status": status,
                    "progress": percent,
                    "payload": payload or {}
                })

            try:
                # Fetch HTML with robust SSL handling
                fetch_result = await fetch_url(url)
                if not fetch_result["ok"]:
                    await progress("error", 100, {"error": fetch_result["error"]})
                    await _ws_send(ws, {"status": "error", "message": fetch_result["error"]})
                    continue

                # Run audit
                await progress("processing", 30, {"message": "Analyzing website..."})
                runner = WebsiteAuditRunner()
                audit_result = await runner.run(url, progress_cb=progress)

                # Add SSL info to result
                audit_result["ssl_relaxed"] = fetch_result["ssl_relaxed"]

                await progress("completed", 100)
                await _ws_send(ws, {
                    "status": "completed",
                    "result": audit_result
                })

            except Exception as e:
                logger.exception(f"Audit failed for {url}")
                await progress("error", 100, {"error": str(e)})
                await _ws_send(ws, {"status": "error", "message": str(e)})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

@app.post("/api/audit/run")
async def api_audit_run(request: AuditRunRequest) -> Dict[str, Any]:
    """REST endpoint for audit (returns full result)"""
    fetch_result = await fetch_url(request.url)
    if not fetch_result["ok"]:
        raise HTTPException(400, detail=fetch_result["error"])

    runner = WebsiteAuditRunner()
    result = await runner.run(request.url)
    result["ssl_relaxed"] = fetch_result["ssl_relaxed"]
    return {"ok": True, "data": result}

@app.post("/api/audit/pdf")
async def api_audit_pdf(request: PdfRequest):
    """Generate and download professional PDF report"""
    url = request.url.strip()
    if not url:
        raise HTTPException(400, detail="URL is required")

    fetch_result = await fetch_url(url)
    if not fetch_result["ok"]:
        raise HTTPException(400, detail=fetch_result["error"])

    try:
        runner = WebsiteAuditRunner()
        audit_result = await runner.run(url)
        audit_result["ssl_relaxed"] = fetch_result["ssl_relaxed"]
    except Exception as e:
        raise HTTPException(500, detail=f"Audit failed: {str(e)}")

    if audit_result.get("error"):
        raise HTTPException(400, detail=audit_result["error"])

    # PDF settings
    report_title = request.report_title.strip() or "Website Audit Report"
    client_name = request.client_name.strip() or "N/A"
    brand_name = request.brand_name.strip() or "FF Tech"
    website_name = request.website_name.strip() or ""
    logo_path = request.logo_path.strip() or None

    # Generate PDF
    tmp_dir = Path(tempfile.mkdtemp(prefix="audit_pdf_"))
    base_name = _safe_filename(website_name or audit_result.get("audited_url") or "audit")
    pdf_path = tmp_dir / f"{base_name}.pdf"

    try:
        pdf_file = generate_pdf_from_runner_result(
            runner_result=audit_result,
            output_path=str(pdf_path),
            logo_path=logo_path,
            report_title=report_title,
            client_name=client_name,
            brand_name=brand_name,
            website_name=website_name or None,
        )
    except Exception as e:
        logger.exception("PDF generation failed")
        raise HTTPException(500, detail=f"PDF generation failed: {str(e)}")

    if not pdf_path.exists():
        raise HTTPException(500, detail="PDF was not created")

    return FileResponse(
        path=pdf_path,
        filename=f"{base_name}.pdf",
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={base_name}.pdf"}
    )

# -----------------------------------------------------------------------------
# Development / Local run
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting server on http://0.0.0.0:{port}")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        # reload=True,  # Uncomment for development only
    )
