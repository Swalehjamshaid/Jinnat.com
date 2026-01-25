
# app/app/main.py
import asyncio
import json
import logging
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.audit.runner import run_audit

logger = logging.getLogger("audit_engine")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="FF Tech Python-Only Audit")

# Static & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def _normalize_url(u: str) -> str:
    """
    Ensure URL has a scheme and looks valid enough for our crawler.
    Adds https:// if missing and checks that netloc exists.
    """
    if not u:
        raise ValueError("Empty URL")
    candidate = u if "://" in u else f"https://{u}"
    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {u}")
    # Keep path if present, ignore query/fragment for the root audit
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path or ''}"


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/open-audit-progress")
async def open_audit_progress(url: str = Query(..., description="Website URL to audit")):
    # Validate/normalize early to fail fast with a clear message
    try:
        normalized_url = _normalize_url(url)
    except Exception as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    async def event_stream():
        # Initial event for the UI
        yield f"data: {json.dumps({'crawl_progress': 0, 'status': 'Starting Python audit...', 'finished': False})}\n\n"

        try:
            # Optional SSE comment to mark start (comment lines start with ':')
            yield f": audit-started {normalized_url}\n\n"

            # Run audit
            result = await run_audit(normalized_url)
            result['finished'] = True

            # Send final result
            yield f"data: {json.dumps(result)}\n\n"
        except Exception as e:
            logger.exception("Audit failed for %s", normalized_url)
            error_payload = {
                "finished": True,
                "error": str(e),
                "status": "Audit failed. Check server logs for details."
            }
            yield f"data: {json.dumps(error_payload)}\n\n"
        finally:
            # Final SSE comment to reduce risk of last-chunk truncation by proxies
            yield f": done\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
