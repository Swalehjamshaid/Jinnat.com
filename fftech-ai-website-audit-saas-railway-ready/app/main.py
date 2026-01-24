# app/app/main.py

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import json
import logging

from app.audit.grader import compute_scores
from app.audit.crawler import crawl  # Python-only async crawler
from app.audit.psi import python_library_audit  # Python-only pre-audit metrics

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
):
    """
    Server-Sent Events endpoint for async audit.
    Fully Python-based:
      1. Crawl
      2. Local audit scoring
    """

    async def event_stream():
        try:
            # Step 1: Start Python pre-audit
            yield f"data: {json.dumps({'crawl_progress': 0, 'status': 'Starting Python audit...'})}\n\n"

            # Run Python pre-audit (head request + static checks)
            pre_audit_metrics = python_library_audit(url)

            # Step 2: Crawl the website
            crawl_result = await crawl(url, max_pages=15)

            crawl_stats = {
                "pages": len(crawl_result.pages),
                "broken_links": len(crawl_result.broken_internal),
                "errors": crawl_result.status_counts.get(0, 0),
            }

            yield f"data: {json.dumps({'crawl_progress': 50, 'status': 'Python crawl complete'})}\n\n"

            # Step 3: Compute final audit score (Python-only)
            overall_score, grade, breakdown = compute_scores(
                lighthouse=pre_audit_metrics,  # Pre-audit metrics used
                crawl=crawl_stats
            )

            yield f"data: {json.dumps({'crawl_progress': 100, 'overall_score': overall_score, 'grade': grade, 'breakdown': breakdown, 'finished': True})}\n\n"

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
