# app/app/main.py

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import time
import json

from app.audit.grader import compute_scores

app = FastAPI(title="FF Tech Audit")

# Static files & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# -----------------------------
# HOME PAGE
# -----------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# -----------------------------
# SSE OPEN AUDIT PROGRESS API
# -----------------------------
@app.get("/api/open-audit-progress")
def open_audit_progress(
    url: str = Query(..., description="Website URL to audit")
):
    """
    Server-Sent Events endpoint.
    Matches frontend EventSource EXACTLY.
    """

    def event_stream():
        try:
            # ---- Simulated crawl progress ----
            for i in range(1, 6):
                progress = i / 5
                yield f"data: {json.dumps({'crawl_progress': progress})}\n\n"
                time.sleep(0.6)

            # ---- Mock audit inputs (replace later with real crawler) ----
            onpage = {
                "missing_title_tags": 1,
                "multiple_h1": 0
            }

            perf = {
                "lcp_ms": 2800
            }

            links = {
                "total_broken_links": 2
            }

            crawl_pages_count = 32

            # ---- Call your EXISTING grader.py ----
            overall_score, grade, breakdown = compute_scores(
                onpage=onpage,
                perf=perf,
                links=links,
                crawl_pages_count=crawl_pages_count
            )

            # ---- Final payload (STRICT frontend contract) ----
            final_payload = {
                "finished": True,
                "overall_score": overall_score,
                "grade": grade,
                "breakdown": breakdown
            }

            yield f"data: {json.dumps(final_payload)}\n\n"

        except Exception as e:
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
def healthz():
    return {"status": "ok"}
