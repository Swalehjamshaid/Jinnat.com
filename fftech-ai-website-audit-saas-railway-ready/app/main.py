from fastapi import FastAPI, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse

from app.audit.grader import compute_scores

app = FastAPI(title="FF Tech Audit")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# =========================
# IN-MEMORY AUDIT STATE
# =========================
audit_jobs = {}

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# =========================
# START AUDIT
# =========================
@app.get("/api/start-open-audit")
def start_audit(url: str = Query(...)):
    audit_jobs[url] = {
        "progress": 0,
        "status": "running",
        "result": None
    }
    return {"started": True, "url": url}


# =========================
# AUDIT PROGRESS
# =========================
@app.get("/api/open-audit-progress")
def audit_progress(url: str = Query(...)):
    if url not in audit_jobs:
        return JSONResponse(
            {"error": "Audit not started"}, status_code=404
        )

    job = audit_jobs[url]

    if job["status"] == "completed":
        return {
            "status": "completed",
            "progress": 100
        }

    # Simulate crawl + analysis steps
    job["progress"] += 20

    if job["progress"] >= 100:
        # ---- REALISTIC SAMPLE DATA ----
        onpage = {
            "missing_title_tags": 1,
            "multiple_h1": 0
        }
        perf = {
            "lcp_ms": 2800
        }
        links = {
            "total_broken_links": 3
        }

        score, grade, breakdown = compute_scores(
            onpage=onpage,
            perf=perf,
            links=links,
            crawl_pages_count=25
        )

        job["result"] = {
            "score": score,
            "grade": grade,
            "breakdown": breakdown
        }
        job["status"] = "completed"
        job["progress"] = 100

        return {
            "status": "completed",
            "progress": 100
        }

    return {
        "status": "running",
        "progress": job["progress"]
    }


# =========================
# FINAL RESULT
# =========================
@app.get("/api/open-audit-result")
def audit_result(url: str = Query(...)):
    job = audit_jobs.get(url)

    if not job or job["status"] != "completed":
        return JSONResponse(
            {"error": "Audit not completed"}, status_code=400
        )

    return job["result"]


@app.get("/healthz")
def healthz():
    return {"ok": True}
