# app/main.py
import json
import logging
import time
import asyncio
from typing import AsyncGenerator
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from app.audit.runner import run_audit

# ─────────────────────────────────────
# Logging
# ─────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("audit_engine")

# ─────────────────────────────────────
# FastAPI App & Lifespan
# ─────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Audit engine starting up...")
    yield
    logger.info("Audit engine shutting down...")

app = FastAPI(
    title="FF Tech International Audit Engine",
    version="2.1",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

# ─────────────────────────────────────
# Static files & Templates
# ─────────────────────────────────────
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ─────────────────────────────────────
# Utilities
# ─────────────────────────────────────
def normalize_url(url: str) -> str:
    if not url:
        raise ValueError("URL is required")

    url = url.strip()
    if "://" not in url:
        url = "https://" + url

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid URL format")

    return f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"


def sse(data: dict) -> str:
    """Format Server-Sent Event payload"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

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
# Audit Event Generator (SSE)
# ─────────────────────────────────────
async def audit_event_generator(url: str) -> AsyncGenerator[str, None]:
    try:
        # Step 1
        yield sse({
            "crawl_progress": 10,
            "status": "Initializing audit engine…",
            "finished": False,
        })
        await asyncio.sleep(0.3)

        # Step 2
        yield sse({
            "crawl_progress": 30,
            "status": "Validating SSL & connectivity…",
            "finished": False,
        })
        await asyncio.sleep(0.4)

        # Step 3
        yield sse({
            "crawl_progress": 55,
            "status": "Fetching and analyzing website…",
            "finished": False,
        })

        # ─── CORE AUDIT EXECUTION ───
        audit_result = await asyncio.to_thread(run_audit, url)

        # Step 4
        yield sse({
            "crawl_progress": 85,
            "status": "Calculating final scores…",
            "finished": False,
        })
        await asyncio.sleep(0.3)

        # Final payload → MUST match index.html JS
        final_payload = {
            "finished": True,
            "crawl_progress": 100,
            "overall_score": audit_result.get("overall_score"),
            "grade": audit_result.get("grade"),
            "breakdown": audit_result.get("breakdown", {}),
            "excel_path": audit_result.get("excel_path"),
            "pptx_path": audit_result.get("pptx_path"),
        }

        yield sse(final_payload)

    except Exception as e:
        logger.exception("Audit failed for %s", url)
        yield sse({
            "finished": True,
            "error": str(e),
            "crawl_progress": 100,
        })

# ─────────────────────────────────────
# Audit API (SSE endpoint)
# ─────────────────────────────────────
@app.get("/api/open-audit-progress")
async def open_audit_progress(
    url: str = Query(..., description="Website URL to audit")
) -> StreamingResponse:
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
            "X-Accel-Buffering": "no",
        },
    )

# ─────────────────────────────────────
# Health Check
# ─────────────────────────────────────
@app.get("/health")
@app.get("/healthz")
async def health():
    return {
        "status": "ok",
        "engine": "FF Tech Audit Engine",
        "version": "2.1",
        "timestamp": time.time(),
    }
