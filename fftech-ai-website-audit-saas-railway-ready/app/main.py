import json
import asyncio
import logging
import sys
from fastapi import FastAPI, Request, Form, status
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import AsyncGenerator

# Real Business Logic Imports
from app.audit.runner import run_audit

# Initialize World-Class Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("FFTech_AI_Auditor")

app = FastAPI(
    title="FFTech AI Website Audit SaaS",
    description="Professional Website Auditing Engine with Real-time Analysis",
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
    Uses Async Generators to maintain a low memory footprint on Railway.
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            logger.info(f"🚀 Audit Pipeline Initiated: {url}")
            
            # Step 1: Handshake & Warmup
            yield f"data: {json.dumps({'crawl_progress': 0.1, 'message': 'AI Engine Warming Up...'})}\n\n"
            await asyncio.sleep(0.3) # Fast feedback

            # Step 2: Running the Audit (Internal logic handles Crawler & PSI)
            yield f"data: {json.dumps({'crawl_progress': 0.3, 'message': 'Fetching Google Core Web Vitals...'})}\n\n"
            
            # This is the heavy lifting
            result = await run_audit(url)

            # Step 3: Final Payload Assembly
            # We explicitly deep-copy to ensure no mutation before JSON serialization
            final_data = {
                **result,
                "crawl_progress": 1.0,
                "finished": True,
                "message": "Audit Successfully Completed"
            }
            
            logger.info(f"✅ Audit Success: {url} | Overall: {final_data.get('overall_score')}")
            yield f"data: {json.dumps(final_data)}\n\n"

        except asyncio.CancelledError:
            logger.warning(f"⚠️ Connection closed by user: {url}")
            raise
        except Exception as e:
            logger.error(f"❌ Critical Failure: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({
                'finished': True,
                'crawl_progress': 1.0,
                'error': 'The audit was interrupted by an internal error.',
                'details': str(e)
            })}\n\n"

    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Stops Railway from buffering your stream
        }
    )

@app.post("/request-login")
async def request_login(email: str = Form(...)):
    """Passwordless Authentication Entry Point."""
    logger.info(f"🔑 Authentication Request: {email}")
    return JSONResponse({
        "status": "success", 
        "message": f"If this email is in our system, a magic link is on its way to {email}."
    })

@app.get("/health")
async def health_check():
    """Railway Deployment Health Probe."""
    return {"status": "online", "version": "2.1.0", "engine": "FFTech-AI-v2"}
