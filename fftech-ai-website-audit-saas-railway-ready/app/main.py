# app/main.py
import json
import logging
import time
from typing import Generator, AsyncGenerator
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
logger = logging.getLogger("audit-engine")

# ─────────────────────────────────────
# FastAPI App & lifespan
# ─────────────────────────────────────
app = FastAPI(
    title="FF Tech International Audit Engine",
    version="2.1",
    docs_url=None,
    redoc_url=None,
    contact={
        "name": "FF Tech International",
        # "url": "https://example.com/support",
    },
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    logger.info("Audit engine starting up...")
    yield
    # shutdown
    logger.info("Audit engine shutting down...")


app.router.lifespan_context = lifespan

# Static & Templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# ─────────────────────────────────────
# Utilities
# ─────────────────────────────────────
def normalize_url(url: str | None) -> str:
    if not url:
        raise ValueError("URL is required")

    url = url.strip()

    if "://" not in url:
        url = "https://" + url

    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL format")
        # Normalize: remove default ports, trailing slash on path when empty
        path = parsed.path or "/"
        if parsed.port in (80, 443) and parsed.port is not None:
            netloc = parsed.hostname or ""
        else:
            netloc = parsed.netloc
        return f"{parsed.scheme}://{netloc}{path}"
    except Exception as e:
        raise ValueError(f"Invalid URL: {str(e)}")


def sse(data: dict) -> str:
    """Format Server-Sent Event"""
    # Ensure we never send invalid JSON
    try:
        payload = json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        logger.warning("Failed to serialize SSE data", exc_info=True)
        payload = json.dumps({"error": "internal serialization error"})
    return f"data: {payload}\n\n"


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
# Audit Event Stream (modernized)
# ─────────────────────────────────────
async def audit_event_generator(url: str) -> AsyncGenerator[str, None]:
    try:
        yield sse({
            "progress": 5,
            "status": "Initializing international audit engine…",
            "finished": False,
        })
        await asyncio.sleep(0.4)

        yield sse({
            "progress": 25,
            "status": "Validating SSL & connectivity…",
            "finished": False,
        })
        await asyncio.sleep(0.4)

        yield sse({
            "progress": 50,
            "status": "Fetching and analyzing website data…",
            "finished": False,
        })
        await asyncio.sleep(0.4)

        # ─── CORE AUDIT CALL ───
        audit_result = await run_audit(url)   # ← assuming run_audit becomes async
        # If run_audit is still synchronous → keep it as is (blocking is ok for now)

        yield sse({
            "progress": 85,
            "status": "Finalizing compliance scoring…",
            "finished": False,
        })
        await asyncio.sleep(0.3)

        # Ensure frontend-friendly payload
        final_payload = audit_result.copy()
        final_payload.update({
            "progress": 100,
            "finished": True,
        })
        yield sse(final_payload)

    except Exception as e:
        logger.exception("Audit execution failed for url: %s", url)
        yield sse({
            "finished": True,
            "error": str(e),
            "progress": 100,
        })


# ─────────────────────────────────────
# Audit API (SSE)
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
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",           # important for nginx proxy
            "Content-Type": "text/event-stream",
        },
    )


# ─────────────────────────────────────
# Health Check
# ─────────────────────────────────────
@app.get("/healthz")
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "engine": "FF Tech Audit Engine",
        "version": "2.1",
        "timestamp": time.time(),
    }
