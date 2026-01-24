# app/app/main.py
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import json
import logging

from app.audit.grader import compute_scores
from app.audit.psi import fetch_lighthouse
from app.audit.crawler import crawl  # Make sure crawl is async

logger = logging.getLogger("audit_engine")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="FF Tech Audit")

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
    url: str = Query(..., description="Website URL to audit"),
    api_key: str = Query(..., description="Google PSI API key")
):
    """
    Server-Sent Events endpoint for async audit.
    Uses async crawler + async Lighthouse fetch.
    """

    async def event_stream():
        try:
            # -----------------------------
            # Start async crawl and Lighthouse fetch concurrently
            # -----------------------------
            crawl_task = asyncio.create_task(crawl(url, max_pages=15))
            psi_task = asyncio.create_task(fetch_lighthouse(url, api_key))

            progress = 0
            yield f"data: {json.dumps({'crawl_progress': progress})}\n\n"

            # Gather results
            crawl_result, psi_result = await asyncio.gather(crawl_task, psi_task)

            # -----------------------------
            # Crawl stats for grader
            # -----------------------------
            crawl_stats = {
                "pages": len(crawl_result.pages),
                "broken_links": len(crawl_result.broken_internal),
                "errors": crawl_result.status_counts.get(0, 0),
            }

            # -----------------------------
            # Compute final audit score
            # -----------------------------
            overall_score, grade, breakdown = compute_scores(
                lighthouse=psi_result,
                crawl=crawl_stats
            )

            # -----------------------------
            # Final payload
            # -----------------------------
            final_payload = {
                "finished": True,
                "overall_score": overall_score,
                "grade": grade,
                "breakdown": breakdown,
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
