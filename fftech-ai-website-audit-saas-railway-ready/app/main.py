# app/app/main.py
import json
import logging
import time
from urllib.parse import urlparse
from typing import Generator

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.audit.runner import run_audit  # synchronous Python-only audit

logger = logging.getLogger("audit_engine")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="FF Tech Python-Only Audit")

# Static files & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def _normalize_url(u: str) -> str:
    """
    Ensure URL has scheme and looks valid.
    Adds https:// if missing; keeps path but strips query/fragment for root audit.
    """
    if not u:
        raise ValueError("Empty URL")
    candidate = u if "://" in u else f"https://{u}"
    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {u}")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path or ''}"


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


def audit_event_generator(url: str) -> Generator[str, None, None]:
    """
    Generator that yields SSE-formatted strings.
    Sends progress updates + final result or error.
    Fully synchronous implementation.
    """
    try:
        # Start
        yield f"data: {json.dumps({'crawl_progress': 0, 'status': 'Starting Python audit...', 'finished': False})}\n\n"
        time.sleep(0.2)

        # Fetching pages
        yield f"data: {json.dumps({'crawl_progress': 10, 'status': 'Fetching page(s)...', 'finished': False})}\n\n"
        time.sleep(0.3)

        # Run full audit
        result = run_audit(url)

        # Processing & final steps
        yield f"data: {json.dumps({'crawl_progress': 80, 'status': 'Analyzing SEO, performance & links...', 'finished': False})}\n\n"
        time.sleep(0.2)

        # Final result
        result['finished'] = True
        yield f"data: {json.dumps(result)}\n\n"

    except Exception as e:
        logger.exception("Audit failed for %s", url)
        error_payload = {
            "finished": True,
            "error": str(e),
            "status": "Audit failed. Check server logs for details."
        }
        yield f"data: {json.dumps(error_payload)}\n\n"

    finally:
        yield f": done\n\n"


@app.get("/api/open-audit-progress")
def open_audit_progress(url: str = Query(..., description="Website URL to audit")):
    """
    SSE endpoint: streams audit progress and final result.
    """
    try:
        normalized_url = _normalize_url(url)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    return StreamingResponse(
        audit_event_generator(normalized_url),
        media_type="text/event-stream"
    )


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
