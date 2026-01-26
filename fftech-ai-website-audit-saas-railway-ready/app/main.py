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

# Import the core logic
from app.audit.runner import run_audit

# ─────────────────────────────────────
# Logging Configuration
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
    logger.info("FF Tech Audit Engine starting up...")
    yield
    logger.info("FF Tech Audit Engine shutting down...")

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
# Ensure these directories exist in your repository
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ─────────────────────────────────────
# Utilities
# ─────────────────────────────────────
def normalize_url(url: str) -> str:
    """Clean and validate the user input URL."""
    if not url:
        raise ValueError("URL is required")

    url = url.strip()
    if "://" not in url:
        url = "https://" + url

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid URL format. Please enter a valid website address.")

    # Ensure path ends with / if empty to prevent redirect loops
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"

def sse_format(data: dict) -> str:
    """Formats the dictionary into a Server-Sent Event compliant string."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

# ─────────────────────────────────────
# Routes
# ─────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the main audit dashboard."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

async def audit_event_generator(url: str) -> AsyncGenerator[str, None]:
    """
    Streams the audit progress to the frontend.
    Runs the blocking 'run_audit' in a separate thread to keep the event loop free.
    """
    try:
        # Step 1: Initialization
        yield sse_format({
            "crawl_progress": 15,
            "status": "Initializing audit engine…",
            "finished": False,
        })
        await asyncio.sleep(0.4)

        # Step 2: Connectivity Check
        yield sse_format({
            "crawl_progress": 35,
            "status": "Validating SSL & connectivity…",
            "finished": False,
        })

        # Step 3: Run the blocking audit function in a thread
        # This prevents the UI from freezing during the network request
        audit_result = await asyncio.to_thread(run_audit, url)

        # Step 4: Analysis
        yield sse_format({
            "crawl_progress": 80,
            "status": "Generating AI insights and scores…",
            "finished": False,
        })
        await asyncio.sleep(0.3)

        # Step 5: Final Packaging
        # We merge everything from runner.py to ensure chart_data, breakdown, 
        # metrics, and ssl_secure reach the frontend.
        final_payload = {
            **audit_result,
            "finished": True,
            "crawl_progress": 100,
            "status": "Success: Audit Complete"
        }

        yield sse_format(final_payload)

    except Exception as e:
        logger.exception("Audit failed for URL: %s", url)
        yield sse_format({
            "finished": True,
            "error": str(e),
            "status": "System Error",
            "crawl_progress": 100,
        })

@app.get("/api/open-audit-progress")
async def open_audit_progress(
    url: str = Query(..., description="Website URL to audit")
) -> StreamingResponse:
    """SSE Endpoint for real-time audit updates."""
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
            "X-Accel-Buffering": "no", # Critical for Railway/Nginx
        },
    )

# ─────────────────────────────────────
# System Endpoints
# ─────────────────────────────────────
@app.get("/health")
@app.get("/healthz")
async def health():
    """Health check for deployment platforms like Railway."""
    return {
        "status": "healthy",
        "engine": "FF Tech International",
        "version": "2.1",
        "server_time": time.time()
    }
