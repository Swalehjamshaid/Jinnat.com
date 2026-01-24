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
    api_key: str = Query(None, description="Google PSI API key, optional")
):
    """
    Server-Sent Events endpoint for async audit.
    Python audit runs first; Google PSI fetch is optional.
    """

    async def event_stream():
        try:
            # -----------------------------
            # Step 1: Crawl the website (Python-only)
            # -----------------------------
            yield f"data: {json.dumps({'crawl_progress': 0, 'psi_progress': 0, 'status': 'Starting Python audit...'})}\n\n"

            crawl_result = await crawl(url, max_pages=15)

            # Prepare crawl stats
            crawl_stats = {
                "pages": len(crawl_result.pages),
                "broken_links": len(crawl_result.broken_internal),
                "errors": crawl_result.status_counts.get(0, 0),
            }

            yield f"data: {json.dumps({'crawl_progress': 100, 'psi_progress': 0, 'status': 'Python audit complete'})}\n\n"

            # -----------------------------
            # Step 2: Compute local audit score (Python only)
            # -----------------------------
            overall_score, grade, breakdown = compute_scores(
                lighthouse=None,  # PSI not yet fetched
                crawl=crawl_stats
            )

            # Yield intermediate results
            yield f"data: {json.dumps({'crawl_progress': 100, 'psi_progress': 0, 'overall_score': overall_score, 'grade': grade, 'breakdown': breakdown, 'finished': False})}\n\n"

            # -----------------------------
            # Step 3: Optional Google PSI / AI audit
            # -----------------------------
            if api_key:
                psi_result = await fetch_lighthouse(url, api_key)
                # Merge PSI results into breakdown
                overall_score, grade, breakdown = compute_scores(
                    lighthouse=psi_result,
                    crawl=crawl_stats
                )

            # -----------------------------
            # Step 4: Final payload
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
