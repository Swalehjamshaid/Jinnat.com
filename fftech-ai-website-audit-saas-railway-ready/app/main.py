
import json
import asyncio
import logging
import sys
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# Real Business Logic Imports
from app.audit.runner import run_audit

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("FFTech_AI_Auditor")

# ---------- App ----------
app = FastAPI(
    title="FFTech AI Website Audit SaaS",
    description="Professional Website Auditing Engine with Real-time Analysis",
    version="2.1.1"
)

# Static and Templates Setup
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# ---------- Helpers ----------
def sse(data: dict) -> str:
    """Serialize a dict as a single SSE event line."""
    return f"data: {json.dumps(data, separators=(',', ':'), ensure_ascii=False)}\n\n"


# ---------- Routes ----------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the modern Dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/open-audit")
async def compat_open_audit(payload: dict):
    """
    Compatibility shim to avoid 404s from older frontends that still POST here.
    We now start audits directly in the SSE endpoint, so this just ACKs.
    """
    url = payload.get("url")
    logger.info(f"Compat /api/open-audit received (no-op). URL={url!r}")
    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "message": "Audit will start via SSE endpoint /api/open-audit-progress",
            "url": url
        }
    )


@app.get("/api/open-audit-progress")
async def open_audit_progress(request: Request, url: str):
    """
    High-Performance SSE Streaming Endpoint (idempotent):
    - Starts the audit in a background task.
    - Streams heartbeats so the UI never looks frozen.
    - Emits final result when done (finished=True).
    """

    # Queue to pass progress/result from the audit task to the SSE generator.
    queue: asyncio.Queue = asyncio.Queue()

    # Caps total runtime so heavy/blocked sites never hang forever.
    MAX_RUNTIME_SECONDS = 60  # tune as needed (Railway + target sites)

    async def audit_task():
        """
        Runs the real audit and pushes updates/results to the queue.
        If your run_audit supports progress callbacks, you can wire them here.
        """
        try:
            # Early-phase coarse updates for perception
            await queue.put({"crawl_progress": 0.05, "status": "Initializing"})
            await asyncio.sleep(0.2)
            await queue.put({"crawl_progress": 0.15, "status": "Fetching HTML & Signals"})

            # ---- Heavy lifting: your real audit ----
            # Make sure run_audit() has internal timeouts for network fetches.
            result = await run_audit(url)
            # ---------------------------------------

            # Final result
            final_data = {
                **result,
                "crawl_progress": 1.0,
                "finished": True,
                "status": "Audit Completed"
            }
            logger.info(f"✅ Audit Success: {url} | Overall: {final_data.get('overall_score')}")
            await queue.put(final_data)

        except Exception as e:
            logger.error(f"❌ Critical Failure while auditing {url}: {e}", exc_info=True)
            await queue.put({
                "finished": True,
                "crawl_progress": 1.0,
                "error": "The audit was interrupted by an internal error.",
                "details": str(e)
            })

    # Start the audit in the background
    task = asyncio.create_task(audit_task())

    # Also enforce a hard timeout on the task
    async def timeout_guard():
        try:
            await asyncio.wait_for(task, timeout=MAX_RUNTIME_SECONDS)
        except asyncio.TimeoutError:
            logger.warning(f"⏰ Audit timed out after {MAX_RUNTIME_SECONDS}s for {url}")
            task.cancel()
            await queue.put({
                "finished": True,
                "crawl_progress": 1.0,
                "error": "Audit timeout",
                "details": f"Exceeded {MAX_RUNTIME_SECONDS}s"
            })

    asyncio.create_task(timeout_guard())

    async def event_generator() -> AsyncGenerator[str, None]:
        """
        Streams queue messages and sends heartbeats so the client sees progress.
        """
        logger.info(f"🚀 Audit Pipeline Initiated: {url}")

        # Initial handshake event
        current_progress = 0.0
        yield sse({"crawl_progress": current_progress, "status": "Queued"})

        try:
            while True:
                # If client disconnected, stop streaming and cancel the task
                if await request.is_disconnected():
                    logger.warning(f"⚠️ Client disconnected during audit: {url}")
                    break

                try:
                    # Wait for audit updates briefly; if none, emit a heartbeat
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                    # Track progress if present
                    if "crawl_progress" in item:
                        try:
                            current_progress = float(item["crawl_progress"])
                        except Exception:
                            pass

                    yield sse(item)

                    # Stop if audit marked finished
                    if item.get("finished"):
                        break

                except asyncio.TimeoutError:
                    # Heartbeat + gentle progress nudge up to 0.9 until we get real updates
                    if current_progress < 0.9:
                        current_progress = min(current_progress + 0.02, 0.9)
                    yield sse({"crawl_progress": round(current_progress, 3), "status": "Working..."})

        finally:
            # Ensure background task is cancelled if still running
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Prevent buffering so SSE stays real-time (Railway/nginx)
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
    return {"status": "online", "version": "2.1.1", "engine": "FFTech-AI-v2"}
