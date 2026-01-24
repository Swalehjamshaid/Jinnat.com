# app/app/main.py

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import json
import logging
import os

from app.audit.grader import compute_scores
from app.audit.psi import fetch_lighthouse
from app.audit.crawler import crawl

logger = logging.getLogger("audit_engine")

app = FastAPI(title="FF Tech Audit")

# Static files & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Load PSI API key from environment (do not expose to frontend)
PSI_API_KEY = os.getenv("PSI_API_KEY")
if not PSI_API_KEY:
    logger.warning("PSI_API_KEY not set! Audits will fail.")


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
async def open_audit_progress(url: str = Query(..., description="Website URL to audit")):
    """
    Server-Sent Events endpoint.
    Async and fast world-class audit.
    """

    async def event_stream():
        try:
            if not PSI_API_KEY:
                yield f"data: {json.dumps({'finished': True, 'error': 'PSI API key not configured'})}\n\n"
                return

            # ---- Start async crawl and Lighthouse fetch ----
            crawl_task = asyncio.create_task(crawl(url, max_pages=15))
            psi_task = asyncio.to_thread(fetch_lighthouse, url, PSI_API_KEY)

            # ---- Report initial progress ----
            yield f"data: {json.dumps({'crawl_progress': 0.0})}\n\n"

            # ---- Await tasks concurrently ----
            crawl_result, psi_result = await asyncio.gather(crawl_task, psi_task)

            # ---- Crawl stats for grader ----
            crawl_stats = {
                "pages": len(crawl_result.pages),
                "broken_links": len(crawl_result.broken_internal),
                "errors": crawl_result.status_counts.get(0, 0),
            }

            # ---- Compute final audit score ----
            overall_score, grade, breakdown = compute_scores(
                lighthouse=psi_result,
                crawl=crawl_stats
            )

            # ---- Send final payload ----
            final_payload = {
                "finished": True,
                "overall_score": overall_score,
                "grade": grade,
                "breakdown": breakdown
            }
            yield f"data: {json.dumps(final_payload)}\n\n"

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
