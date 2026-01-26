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
# Import our fully integrated audit pipeline
from app.audit.runner import run_audit
# ─────────────────────────────────────────────
# Logging Configuration
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("audit_engine")
# ─────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FF Tech International Audit Engine starting…")
    yield
    logger.info("FF Tech International Audit Engine stopping…")
app = FastAPI(
    title="FF Tech International Audit Engine",
    version="3.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)
# ─────────────────────────────────────────────
# Static Files + Templates
# ─────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
# ─────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────
def normalize_url(url: str) -> str:
    """Clean & validate URLs before crawling."""
    if not url:
        raise ValueError("URL cannot be empty.")
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid URL format.")
    # Ensure consistent trailing slash
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"
def sse_format(data: dict) -> str:
    """Format Safe Server-Sent Event output."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
# ─────────────────────────────────────────────
# Home Page
# ─────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
# ─────────────────────────────────────────────
# SSE Audit Stream
# ─────────────────────────────────────────────
async def audit_event_generator(url: str) -> AsyncGenerator[str, None]:
    """
    Streams audit progress to frontend.
    Runs run_audit() in background threads to avoid blocking.
    """
    try:
        # ── Dummy first event + tiny delay ── helps many nginx/railway proxies flush
        yield sse_format({
            "crawl_progress": 0,
            "status": "Connecting...",
            "finished": False,
        })
        await asyncio.sleep(0.15)

        # Initial message
        yield sse_format({
            "crawl_progress": 10,
            "status": "Starting engine…",
            "finished": False,
        })
        await asyncio.sleep(0.3)
        yield sse_format({
            "crawl_progress": 30,
            "status": "Checking network & SSL…",
            "finished": False,
        })
        await asyncio.sleep(0.4)
        # Run our main audit pipeline (crawler + SEO + performance + charts)
        audit_result = await asyncio.to_thread(run_audit, url)
        yield sse_format({
            "crawl_progress": 80,
            "status": "Building charts & insights…",
            "finished": False,
        })
        await asyncio.sleep(0.3)
        # Final SSE payload sent to index.html
        final_payload = {
            **audit_result,
            "finished": True,
            "crawl_progress": 100,
            "status": "Audit Complete ✔"
        }
        yield sse_format(final_payload)
    except Exception as e:
        logger.exception("Audit failed for %s", url)
        yield sse_format({
            "finished": True,
            "error": str(e),
            "crawl_progress": 100,
            "status": "Audit failed."
        })
# ─────────────────────────────────────────────
# SSE Endpoint
# ─────────────────────────────────────────────
@app.get("/api/open-audit-progress")
async def open_audit_progress(url: str = Query(..., description="Website URL to audit")) -> StreamingResponse:
    try:
        normalized = normalize_url(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return StreamingResponse(
        audit_event_generator(normalized),
        media_type="text/event-stream",
        headers={
            # Very aggressive anti-buffering set – many combinations reported working on Railway
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",

            # Railway / nginx / reverse-proxy specific
            "X-Accel-Buffering": "no",
            "X-Proxy-Buffering": "no",
            "Proxy-Buffering": "off",
            "X-Accel-Charset": "utf-8",
            "X-Accel-Limit-Rate": "0",
        }
    )
# ─────────────────────────────────────────────
# Health Checks (Railway/Render/Azure)
# ─────────────────────────────────────────────
@app.get("/health")
@app.get("/healthz")
async def health():
    return {
        "status": "ok",
        "engine": "FF Tech Audit Engine",
        "version": "3.0",
        "time": time.time(),
    }
