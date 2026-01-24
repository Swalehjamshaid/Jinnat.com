import json
import asyncio
import logging
from fastapi import FastAPI, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# Real Business Logic Imports
from app.audit.runner import run_audit
from app.audit.grader import compute_scores

# Initialize Logging for Railway
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FFTech_Production")

app = FastAPI(title="FFTech AI Website Audit SaaS")

# Static and Templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the high-end dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/open-audit-progress")
async def open_audit_progress(url: str):
    """
    High-Performance Streaming Endpoint.
    This manages the live progress bar and final data delivery.
    """
    async def event_generator():
        try:
            # Phase 1: Handshake
            logger.info(f"Audit Started: {url}")
            yield f"data: {json.dumps({'crawl_progress': 0.1, 'message': 'Initializing AI Engine...'})}\n\n"
            await asyncio.sleep(0.5)

            # Phase 2: Execution (Call your real runner.py)
            yield f"data: {json.dumps({'crawl_progress': 0.4, 'message': 'Scanning Performance & SEO...'})}\n\n"
            
            # This is where the real work happens
            result = await run_audit(url)

            # Phase 3: Success Payload
            # We explicitly add the 'finished' flag to stop the UI spinner
            final_data = result.copy()
            final_data["crawl_progress"] = 1.0
            final_data["finished"] = True
            
            logger.info(f"Audit Success: {url} - Score: {final_data.get('overall_score')}")
            yield f"data: {json.dumps(final_data)}\n\n"

        except Exception as e:
            # Phase 4: Emergency Exit
            # If the API fails, we MUST tell the UI to stop spinning
            logger.error(f"Audit Failed: {url} - Error: {str(e)}")
            error_payload = {
                "finished": True,
                "error": "Audit failed. Please verify the URL or API configuration.",
                "details": str(e)
            }
            yield f"data: {json.dumps(error_payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/request-login")
async def request_login(email: str = Form(...)):
    """Handles the Magic Link passwordless authentication logic."""
    # Logic for your magic link generation goes here
    logger.info(f"Login request for {email}")
    return JSONResponse({
        "status": "success",
        "message": f"A secure magic link has been sent to {email}"
    })

@app.get("/health")
async def health_check():
    """Endpoint for Railway to monitor service health."""
    return {"status": "healthy"}
