
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
    """
    if not u:
        raise ValueError("Empty URL")
    parsed = urlparse(u if "://" in u else f"https://{u}")
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {u}")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path or ''}"

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/open-audit-progress")
async def open_audit_progress(url: str = Query(..., description="Website URL to audit")):
    # Basic normalization/validation
    try:
        normalized_url = _normalize_url(url)
    except Exception as ve:
        # Let the client know immediately with a 400
        raise HTTPException(status_code=400, detail=str(ve))

    async def event_stream():
        # Initial progress event
        yield f"data: {json.dumps({'crawl_progress': 0, 'status': 'Starting Python audit...', 'finished': False})}\n\n"

        # Heartbeat task to keep SSE alive
        async def heartbeat():
            try:
                while True:
                    await asyncio.sleep(15)
                    yield f": ping\n\n"  # SSE comment line; keeps connection open without affecting client JSON
            except asyncio.CancelledError:
                return

        # Note: StreamingResponse will iterate this generator. We can interleave heartbeats
        # by yielding from the heartbeat generator while awaiting run_audit.
        # Simpler approach: occasional sleeps and heartbeats in-line.

        try:
            # Optional: a tiny heartbeat before long tasks start
            yield f": audit-started {normalized_url}\n\n"

            # Run the audit
            result = await run_audit(normalized_url)
            result['finished'] = True

            yield f"data: {json.dumps(result)}\n\n"
        except Exception as e:
            logger.exception("Audit failed for %s", normalized_url)
            error_payload = {
                "finished": True,
                "error": str(e),
                "status": "Audit failed. Check logs for details."
            }
            yield f"data: {json.dumps(error_payload)}\n\n"
        finally:
            # Final heartbeat so intermediaries don’t cut off the last message
            yield f": done\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
``
