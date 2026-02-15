# -*- coding: utf-8 -*-
"""
app/main.py
Fully integrated FastAPI app for Website Audit Pro
- Serves index.html from app/templates/index.html
- WebSocket /ws for live progress & results
- REST fallback /api/audit/run
- PDF generation /api/audit/pdf (safe, enriched in runner.py)
- Robust logging & error handling for Railway
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import time
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

# Import runner + PDF helper
from app.audit.runner import WebsiteAuditRunner, generate_pdf_from_runner_result

# -----------------------------------------------------------------------------
# Logging (Railway-visible)
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("website-audit-pro")

# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
app = FastAPI(title="Website Audit Pro", version="2.2.0")

# CORS (UI is same host on Railway, but allow * for safety)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip for smaller JSON payloads
app.add_middleware(GZipMiddleware, minimum_size=800)

BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML_PATH = BASE_DIR / "templates" / "index.html"

# -----------------------------------------------------------------------------
# Simple in-memory cache (TTL-based), shared by WS + REST + PDF
# -----------------------------------------------------------------------------
CACHE_TTL_SECONDS = int(os.getenv("AUDIT_CACHE_TTL_SECONDS", "900"))
_audit_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    item = _audit_cache.get(key)
    if not item:
        return None
    ts, val = item
    if (time.time() - ts) > CACHE_TTL_SECONDS:
        _audit_cache.pop(key, None)
        return None
    return val


def _cache_set(key: str, value: Dict[str, Any]) -> None:
    _audit_cache[key] = (time.time(), value)


def _safe_filename(name: str, default: str = "audit_report") -> str:
    name = (name or "").strip() or default
    name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name).strip("._-") or default
    return name[:90]


def _runner_error_message(result: Dict[str, Any]) -> Optional[str]:
    return str(result.get("error")) if result.get("error") else None


async def _ws_send(ws: WebSocket, message: Dict[str, Any]) -> None:
    """Send JSON to WS; swallow transient send errors."""
    try:
        await ws.send_text(json.dumps(message, ensure_ascii=False))
    except Exception:
        # Client might have gone away
        pass


# -----------------------------------------------------------------------------
# Prefetch HTML (strict SSL first, then insecure, with clear reason)
# -----------------------------------------------------------------------------
def _fetch_html(url: str) -> Tuple[bool, str, str]:
    """
    Returns: (success, html_text, mode_or_error)
      mode_or_error is either "strict" | "insecure" | error message
    """
    headers = {
        "User-Agent": "FFTechAuditBot/2.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        r = requests.get(url, timeout=20, headers=headers, allow_redirects=True, verify=True)
        r.raise_for_status()
        return True, r.text, "strict"
    except requests.exceptions.SSLError:
        try:
            r = requests.get(url, timeout=20, headers=headers, allow_redirects=True, verify=False)
            r.raise_for_status()
            return True, r.text, "insecure"
        except Exception as e:
            return False, "", f"Fetch failed (insecure): {str(e)}"
    except Exception as e:
        return False, "", f"Fetch failed: {str(e)}"


# -----------------------------------------------------------------------------
# Pydantic models
# -----------------------------------------------------------------------------
class AuditRunRequest(BaseModel):
    url: str = Field(..., description="Website URL")


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
@app.get("/health", response_class=JSONResponse)
async def health() -> Dict[str, Any]:
    return {"ok": True, "version": app.version}


@app.get("/version", response_class=PlainTextResponse)
async def version() -> str:
    return app.version or "0.0.0"


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
# -----------------------------------------------------------------------------
@app.websocket("/ws")
async def ws_audit(ws: WebSocket):
    await ws.accept()
    runner = WebsiteAuditRunner()
    logger.info("WebSocket client connected.")
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

            # Serve from cache if valid
            cached = _cache_get(url)
            if cached and not _runner_error_message(cached):
                await _ws_send(ws, {"status": "completed", "progress": 100, "result": cached})
                continue

            # Progress callback to stream to WS
            async def progress_cb(status: str, percent: int, payload: Optional[dict] = None):
                await _ws_send(ws, {"status": status, "progress": int(percent), "payload": payload})

            try:
                # Prefetch HTML for deterministic scoring
                await progress_cb("fetching", 10, {"message": "Fetching HTML..."})
                success, html_content, fetch_mode = _fetch_html(url)
                if not success:
                    await _ws_send(ws, {
                        "status": "error",
                        "progress": 100,
                        "payload": {"error": f"Could not fetch page: {fetch_mode}"}
                    })
                    continue

                await progress_cb("fetched", 20, {"message": f"HTML fetched ({fetch_mode}), length: {len(html_content)}"})

                # Run runner (keeps IO contract unchanged)
                result = await runner.run(url, html=html_content, progress_cb=progress_cb)
                _cache_set(url, result)

                # Error from runner?
                err = _runner_error_message(result)
                if err:
                    await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": err}})
                    continue

                await _ws_send(ws, {"status": "completed", "progress": 100, "result": result})

            except Exception as e:
                logger.exception("WebSocket audit error")
                await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": str(e)}})
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        logger.exception("WebSocket closed with error: %s", e)


# -----------------------------------------------------------------------------
# REST: /api/audit/run  (fallback used by UI when WS not available)
# -----------------------------------------------------------------------------
@app.post("/api/audit/run")
async def api_audit_run(req: AuditRunRequest) -> JSONResponse:
    url = (req.url or "").strip()
    if not url:
        return JSONResponse({"error": "Empty URL"}, status_code=400)

    cached = _cache_get(url)
    if cached:
        return JSONResponse(cached)

    runner = WebsiteAuditRunner()
    success, html_content, fetch_mode = _fetch_html(url)
    if not success:
        return JSONResponse({"error": f"Could not fetch page: {fetch_mode}"}, status_code=400)

    try:
        result = await runner.run(url, html=html_content, progress_cb=None)
        _cache_set(url, result)
        return JSONResponse(result)
    except Exception as e:
        logger.exception("REST audit error")
        return JSONResponse({"error": str(e)}, status_code=500)


# -----------------------------------------------------------------------------
# PDF: /api/audit/pdf  (uses cached audit or runs fresh, then calls generate_pdf_from_runner_result)
# -----------------------------------------------------------------------------
@app.post("/api/audit/pdf")
async def api_audit_pdf(req: PdfRequest):
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    logger.info(f"PDF request received for URL: {url}")

    runner_result = _cache_get(url)
    if runner_result is None:
        logger.info(f"No cache hit for {url} → running fresh audit")
        runner = WebsiteAuditRunner()
        success, html_content, fetch_mode = _fetch_html(url)
        if not success:
            logger.error(f"Fetch failed for PDF: {fetch_mode}")
            raise HTTPException(status_code=400, detail=f"Could not fetch page: {fetch_mode}")
        try:
            runner_result = await runner.run(url, html=html_content, progress_cb=None)
            _cache_set(url, runner_result)
            logger.info(f"Audit completed for PDF: {url}")
        except Exception as e:
            logger.exception("Audit failed during PDF generation")
            raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")

    err = _runner_error_message(runner_result)
    if err:
        logger.warning(f"Audit error for PDF: {err}")
        raise HTTPException(status_code=400, detail=f"Audit error: {err}")

    # Validate runner_result structure
    if not isinstance(runner_result, dict) or "overall_score" not in runner_result:
        logger.error("Invalid runner_result structure for PDF")
        raise HTTPException(status_code=500, detail="Invalid audit result structure")

    report_title = (req.report_title or "").strip() or "Website Audit Report"
    logo_path = (req.logo_path or "").strip() or None

    tmp_dir = Path(tempfile.mkdtemp(prefix="audit_pdf_"))
    fname = _safe_filename(url or "audit_report")
    pdf_path = tmp_dir / f"{fname}.pdf"

    logger.info(f"Generating PDF at: {pdf_path}")

    try:
        pdf_generated_path = generate_pdf_from_runner_result(
            runner_result,
            output_path=str(pdf_path),
            logo_path=logo_path,
            report_title=report_title,
        )
        logger.info(f"PDF successfully generated: {pdf_generated_path}")
    except ImportError:
        logger.error("PDF generation failed: reportlab not installed")
        raise HTTPException(
            status_code=500,
            detail="PDF library (reportlab) is missing. Add 'reportlab' to requirements.txt and redeploy."
        )
    except RuntimeError as e:
        logger.error(f"PDF runtime error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF generation runtime error: {str(e)}")
    except Exception as e:
        logger.exception("PDF generation failed")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    if not pdf_path.exists():
        logger.error("PDF file was not created")
        raise HTTPException(status_code=500, detail="PDF file was not created")

    logger.info(f"Serving PDF file: {pdf_path}")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
        headers={"Content-Disposition": f'attachment; filename="{pdf_path.name}"'},
    )


# -----------------------------------------------------------------------------
# Local dev entry (Railway uses Procfile/Start cmd)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    # IMPORTANT: uvicorn (ASGI) is required for WebSockets
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
