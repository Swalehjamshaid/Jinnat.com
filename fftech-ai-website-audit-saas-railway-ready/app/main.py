# app/main.py

import json
import logging
import time
from typing import Generator
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.audit.runner import run_audit

# ─────────────────────────────────────
# Logging
# ─────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("audit_engine")

# ─────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────
app = FastAPI(
    title="FF Tech International Audit Engine",
    version="2.1",
    docs_url=None,
    redoc_url=None,
)

# Static & Templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ─────────────────────────────────────
# Utilities
# ─────────────────────────────────────
def normalize_url(url: str) -> str:
    if not url:
        raise ValueError("URL is required")

    if "://" not in url:
        url = "https://" + url

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid URL format")

    return f"{parsed.scheme}://{parsed.netloc}{parsed.path or ''}"


def sse(data: dict) -> str:
    """Format Server-Sent Event"""
    return f"data: {json.dumps(data)}\n\n"

# ─────────────────────────────────────
# Home Page
# ─────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

# ─────────────────────────────────────
# Audit Event Stream
# ─────────────────────────────────────
def audit_event_generator(url: str) -> Generator[str, None, None]:
    try:
        yield sse({
            "progress": 5,
            "status": "Initializing international audit engine…",
            "finished": False,
        })
        time.sleep(0.4)

        yield sse({
            "progress": 25,
            "status": "Validating SSL & connectivity…",
            "finished": False,
        })
        time.sleep(0.4)

        yield sse({
            "progress": 50,
            "status": "Fetching and analyzing website data…",
            "finished": False,
        })
        time.sleep(0.4)

        # 🔹 CORE AUDIT CALL
        audit_result = run_audit(url)

        yield sse({
            "progress": 85,
            "status": "Finalizing compliance scoring…",
            "finished": False,
        })
        time.sleep(0.3)

        # Ensure frontend-friendly payload
        audit_result.update({
            "progress": 100,
            "finished": True,
        })

        yield sse(audit_result)

    except Exception as e:
        logger.exception("Audit execution failed")
        yield sse({
            "finished": True,
            "error": str(e),
        })

# ─────────────────────────────────────
# Audit API (SSE)
# ─────────────────────────────────────
@app.get("/api/open-audit-progress")
async def open_audit_progress(url: str = Query(..., description="Website URL")):
    try:
        normalized_url = normalize_url(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return StreamingResponse(
        audit_event_generator(normalized_url),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

# ─────────────────────────────────────
# Health Check
# ─────────────────────────────────────
@app.get("/healthz")
async def health():
    return {
        "status": "ok",
        "engine": "FF Tech Audit Engine",
        "version": "2.1",
    }
