# app/app/main.py
import json
import logging
import time
from urllib.parse import urlparse
from typing import Generator, AsyncGenerator

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.audit.runner import run_audit_async  # updated async SSL-verified audit

# ─────────────────────────────────────
# Logging setup
# ─────────────────────────────────────
logger = logging.getLogger("audit_engine")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

# ─────────────────────────────────────
# FastAPI app initialization
# ─────────────────────────────────────
app = FastAPI(title="FF Tech SSL-Verified Audit", version="3.0")

# Static files & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ─────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────
def _normalize_url(u: str) -> str:
    """Normalize URL for audit: add https:// if missing, keep scheme + netloc + path only."""
    if not u:
        raise ValueError("Empty URL")
    candidate = u if "://" in u else f"https://{u}"
    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {u}")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path or ''}"

# ─────────────────────────────────────
# Home route
# ─────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Render main audit homepage."""
    return templates.TemplateResponse("index.html", {"request": request})

# ─────────────────────────────────────
# Async SSE Generator for audit progress
# ─────────────────────────────────────
async def audit_event_generator_async(url: str) -> AsyncGenerator[str, None]:
    """
    Yield Server-Sent Events (SSE) strings with progress updates and final audit result.
    Fully async using SSL-verified HTTP requests.
    """
    try:
        # Start
        yield f"data: {json.dumps({'crawl_progress': 0, 'status': 'Initializing audit...', 'finished': False})}\n\n"
        await asyncio.sleep(0.2)

        # Fetching pages
        yield f"data: {json.dumps({'crawl_progress': 10, 'status': 'Fetching pages...', 'finished': False})}\n\n"
        await asyncio.sleep(0.3)

        # Run full async audit
        result_html = await run_audit_async(url)

        # Processing & final steps
        yield f"data: {json.dumps({'crawl_progress': 80, 'status': 'Analyzing SEO, performance & links...', 'finished': False})}\n\n"
        await asyncio.sleep(0.2)

        # Final result
        result_payload = {
            "finished": True,
            "status": "Audit completed successfully.",
            "length": len(result_html)
        }
        yield f"data: {json.dumps(result_payload)}\n\n"

    except Exception as e:
        logger.exception("Audit failed for %s", url)
        error_payload = {
            "finished": True,
            "error": str(e),
            "status": "Audit failed. Check server logs for details."
        }
        yield f"data: {json.dumps(error_payload)}\n\n"

    finally:
        # End of stream
        yield f": done\n\n"

# ─────────────────────────────────────
# SSE Endpoint
# ─────────────────────────────────────
@app.get("/api/open-audit-progress")
async def open_audit_progress(url: str = Query(..., description="Website URL to audit")):
    """
    Async SSE endpoint that streams SSL-verified audit progress + final result.
    Returns: StreamingResponse with text/event-stream
    """
    try:
        normalized_url = _normalize_url(url)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    return StreamingResponse(
        audit_event_generator_async(normalized_url),
        media_type="text/event-stream"
    )

# ─────────────────────────────────────
# Health check
# ─────────────────────────────────────
@app.get("/healthz")
def healthz():
    return {"status": "ok"}
