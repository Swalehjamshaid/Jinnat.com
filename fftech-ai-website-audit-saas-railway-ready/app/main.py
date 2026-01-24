import json
import asyncio
import logging
from fastapi import FastAPI, Request, Form, status
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# Real Business Logic Imports
from app.audit.runner import run_audit

# Initialize World-Class Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("FFTech_AI_Auditor")

app = FastAPI(
    title="FFTech AI Website Audit SaaS",
    description="Professional Website Auditing Engine",
    version="2.1.0"
)

# Static and Templates Setup
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the modern Dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/open-audit-progress")
async def open_audit_progress(url: str):
    """
    High-Performance SSE Streaming Endpoint.
    Orchestrates the real-time feedback loop between Python and the Dashboard.
    """
    async def event_generator():
        try:
            logger.info(f"🚀 Audit Request Received: {url}")
            
            # Step 1: Handshake
            yield f"data: {json.dumps({'crawl_progress': 0.1, 'message': 'Waking up AI Engine...'})}\n\n"
            await asyncio.sleep(0.5)

            # Step 2: Running the Multi-Step Audit
            yield f"data: {json.dumps({'crawl_progress': 0.3, 'message': 'Connecting to Google PageSpeed...' })}\n\n"
            
            # Perform the real audit using your runner.py logic
            result = await run_audit(url)

            # Step 3: Result Delivery
            # Ensure the 'finished' flag is True so the UI spinner stops immediately
            final_data = result.copy()
            final_data["crawl_progress"] = 1.0
            final_data["finished"] = True
            
            logger.info(f"✅ Audit Successful: {url} | Score: {final_data.get('overall_score')}")
            yield f"data: {json.dumps(final_data)}\n\n"

        except Exception as e:
            # Emergency Shutdown of the Spinner
            logger.error(f"❌ Audit Failed for {url}: {str(e)}", exc_info=True)
            error_payload = {
                "finished": True,
                "crawl_progress": 1.0,
                "error": "Scan Interrupted",
                "details": "Please check your URL or API quota settings."
            }
            yield f"data: {json.dumps(error_payload)}\n\n"

    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no" # Essential for Railway/Nginx streaming
        }
    )

@app.post("/request-login")
async def request_login(email: str = Form(...)):
    """Handles Passwordless Magic Link requests."""
    logger.info(f"🔑 Magic link requested for user: {email}")
    # Integration point for SendGrid/Mailgun would go here
    return JSONResponse({
        "status": "success",
        "message": f"If an account exists for {email}, a magic link has been sent."
    })

@app.get("/health")
async def health_check():
    """Railway Health Check Endpoint."""
    return {"status": "online", "engine": "FFTech-AI-v2"}

# Image of a Server-Sent Events (SSE) data flow diagram
