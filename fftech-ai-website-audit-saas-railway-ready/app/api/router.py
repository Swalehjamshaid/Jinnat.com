
# app/api/routes.py
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
from typing import Dict, Any
from contextlib import suppress
import json
import logging

logger = logging.getLogger("FFTech_Production")
router = APIRouter()

# In-memory job registry. For production, prefer Redis.
_jobs: Dict[str, Dict[str, Any]] = {}

def json_dumps(obj) -> str:
    """Compact JSON for SSE."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)

# ====== Replace this with your real logic in audit_runner if you have it ====== #
# You can import your own runner and call it from here.
async def run_audit_and_emit(url: str, queue: asyncio.Queue):
    """
    Start the audit for a URL and push progress updates + final result to `queue`.
    This is a safe template; replace the simulated sections with real steps.
    Make sure your real network calls have timeouts.
    """
    async def emit_progress(pct: int, status: str = None):
        payload = {"crawl_progress": pct / 100}
        if status:
            payload["status"] = status
        await queue.put(payload)

    try:
        logger.info(f"Audit Started: {url}")
        await emit_progress(5, "Initializing")

        # --- Fetch HTML (set timeouts to avoid hanging) ---
        await emit_progress(20, "Fetching HTML")
        await asyncio.sleep(0.8)  # <-- replace with your fetch_html(url, timeout=15000)

        # --- Parse & collect signals ---
        await emit_progress(50, "Parsing & Signals")
        await asyncio.sleep(0.8)  # <-- parse html, extract metrics, etc.

        # --- Compute scores ---
        await emit_progress(75, "Scoring")
        await asyncio.sleep(0.6)  # <-- compute On-page/Performance/Coverage/Confidence

        # Build final payload (replace with real results)
        result = {
            "overall_score": 86,
            "grade": "B+",
            "breakdown": {
                "onpage": 88,
                "performance": 79,
                "coverage": 83,
                "confidence": 70
            },
            "finished": True,
            "crawl_progress": 1.0
        }
        await queue.put(result)

    except Exception as exc:
        logger.exception("Audit failed")
        await queue.put({
            "error": str(exc),
            "finished": True,
            "crawl_progress": 1.0
        })

@router.get("/api/open-audit-progress")
async def open_audit_progress(request: Request, url: str):
    """
    Idempotent SSE endpoint:
      - If there is no running job for `url`, starts it.
      - Streams progress events + final result.
    """
    # Start a new job if none exists or last one finished
    if url not in _jobs or _jobs[url]["task"].done():
        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(run_audit_and_emit(url, queue))
        _jobs[url] = {"task": task, "queue": queue}

    queue = _jobs[url]["queue"]
    task = _jobs[url]["task"]

    async def event_stream():
        try:
            # Initial heartbeat improves perceived responsiveness
            yield f"data: {json_dumps({'crawl_progress':0.0,'status':'Queued'})}\n\n"
            while True:
                # Client disconnected?
                if await request.is_disconnected():
                    break

                # Wait for next message; timeout to allow loop to check disconnections
                with suppress(asyncio.TimeoutError):
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json_dumps(item)}\n\n"
                    if item.get("finished"):
                        break
        finally:
            # Optional: cleanup finished jobs
            if task.done():
                # Keep a small cache window if you want to allow re-attach
                # For now, we just leave it in memory; or uncomment:
                # _jobs.pop(url, None)
                pass

    return StreamingResponse(event_stream(), media_type="text/event-stream")
