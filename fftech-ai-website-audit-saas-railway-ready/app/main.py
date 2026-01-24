from fastapi import FastAPI, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.audit.grader import compute_scores  # Your grader function

import asyncio
import random
import json

app = FastAPI(title="FFTech AI Website Audit SaaS")

# Serve static files (CSS/JS/img)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates folder
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Render the main dashboard page (index.html)
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/open-audit-progress")
async def open_audit_progress(url: str):
    """
    Simulated SSE (Server-Sent Events) endpoint for live progress updates.
    Replace this simulation with your actual website audit logic.
    """
    async def event_generator():
        total_pages = random.randint(5, 25)
        for i in range(1, total_pages + 1):
            crawl_progress = i / total_pages
            data = {"crawl_progress": crawl_progress, "finished": False}
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(0.1)

        # Compute final scores using your grader function
        onpage_metrics = {"missing_title_tags": 0, "multiple_h1": 1}
        perf_metrics = {"lcp_ms": random.randint(1200, 4000)}
        links_metrics = {"total_broken_links": random.randint(0, 5)}

        overall_score, grade, breakdown = compute_scores(
            onpage_metrics, perf_metrics, links_metrics, crawl_pages_count=total_pages
        )

        final_data = {
            "crawl_progress": 1,
            "finished": True,
            "overall_score": overall_score,
            "grade": grade,
            "breakdown": breakdown
        }

        yield f"data: {json.dumps(final_data)}\n\n"

    return HTMLResponse(content=event_generator(), media_type="text/event-stream")


@app.post("/request-login")
async def request_login(email: str = Form(...)):
    """
    Passwordless login: sends a magic link to the provided email.
    """
    # TODO: integrate with real email sending
    return JSONResponse({"message": f"Magic link sent to {email}"})
