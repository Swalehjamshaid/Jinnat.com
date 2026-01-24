# app/app/main.py
import asyncio
import json
import logging

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.audit.grader import compute_scores
from app.audit.runner import run_audit

logger = logging.getLogger("audit_engine")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="FF Tech Python-Only Audit")

# Static files & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# -----------------------------
# HOME PAGE
# -----------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# -----------------------------
# SSE OPEN AUDIT PROGRESS API
# -----------------------------
@app.get("/api/open-audit-progress")
async def open_audit_progress(
    url: str = Query(..., description="Website URL to audit")
):
    """
    Server-Sent Events endpoint for async audit.
    Python-native audit only (no Google PSI required).
    """

    async def event_stream():
        try:
            # Step 0: Notify client
            yield f"data: {json.dumps({'crawl_progress': 0, 'status': 'Starting Python audit...'})}\n\n"

            # Step 1: Run audit
            result = await run_audit(url)

            # Step 2: Send final result
            yield f"data: {json.dumps(result)}\n\n"

        except Exception as e:
            logger.exception(f"Audit failed for {url}")
            error_payload = {
                "finished": True,
                "error": str(e)
            }
            yield f"data: {json.dumps(error_payload)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# -----------------------------
# HEALTH CHECK
# -----------------------------
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
