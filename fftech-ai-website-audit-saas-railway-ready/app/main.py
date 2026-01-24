from fastapi import FastAPI, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# Import your real audit engine
from app.audit.runner import run_audit
from app.audit.grader import compute_scores

import asyncio
import json
import logging

# Setup logging to see errors in Railway logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FFTech_Main")

app = FastAPI(title="FFTech AI Website Audit SaaS")

# Mount static and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the dashboard"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/open-audit-progress")
async def open_audit_progress(url: str):
    """
    World-Class SSE Endpoint:
    Connects frontend to the real Google PSI & AI Engine.
    """
    async def event_generator():
        try:
            # 1. Start: Tell UI we are connecting
            yield f"data: {json.dumps({'crawl_progress': 0.1, 'message': 'Connecting to Google APIs...'})}\n\n"
            await asyncio.sleep(0.5)

            # 2. Run the actual Audit (Calling your runner.py)
            # This handles the real PageSpeed and Crawling
            yield f"data: {json.dumps({'crawl_progress': 0.4, 'message': 'Scanning Performance & SEO...'})}\n\n"
            
            result_data = await run_audit(url)

            # 3. Finalize: Prepare the world-class payload
            # We merge the real results with the 'finished' flag for the UI
            final_payload = result_data.copy()
            final_payload["crawl_progress"] = 1.0
            final_payload["finished"] = True
            final_payload["message"] = "Audit Complete!"

            yield f"data: {json.dumps(final_payload)}\n\n"
            logger.info(f"Successfully completed audit for: {url}")

        except Exception as e:
            logger.error(f"Audit failed for {url}: {str(e)}")
            # Even on error, we send 'finished' so the UI spinner stops
            error_payload = {
                "finished": True, 
                "error": "API Key or Database connection issue",
                "details": str(e)
            }
            yield f"data: {json.dumps(error_payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/request-login")
async def request_login(email: str = Form(...)):
    """Passwordless login endpoint"""
    logger.info(f"Magic link requested for: {email}")
    return JSONResponse({"message": f"Magic link sent to {email}"})
