
# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
from contextlib import suppress
from typing import Dict, Any
import json
import logging

from app.audit.runner import run_audit

log = logging.getLogger("FFTech_AI_Auditor")

app = FastAPI()

# In-memory job registry (use Redis for multi-instance)
_jobs: Dict[str, Dict[str, Any]] = {}

def _json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)

@app.post("/api/open-audit")
async def compat_open_audit(request: Request):
    """
    Compat endpoint (since your front-end sometimes POSTs here).
    We accept the URL but do not start the job because the SSE does it.
    Returns 202 to avoid 404 noise in logs.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    url = body.get("url")
    log.info("FFTech_AI_Auditor: Compat /api/open-audit received (no-op). URL='%s'", url)
    return JSONResponse({"status": "accepted", "url": url}, status_code=202)

@app.get("/api/open-audit-progress")
async def open_audit_progress(request: Request, url: str):
    """
    SSE endpoint that:
    1) Creates/starts a job for the URL if needed
    2) Streams progress + final result
    """
    if url not in _jobs or _jobs[url]["task"].done():
        queue: asyncio.Queue = asyncio.Queue()

        async def producer():
            try:
                # Stage updates (UI-friendly)
                await queue.put({"crawl_progress": 0.05, "status": "Initializing"})
                # You can add more granular stages by splitting run_audit logic if desired
                result = await run_audit(url)
                await queue.put(result)
            except Exception as exc:
                log.exception("❌ Critical Failure while auditing %s: %s", url, exc)
                await queue.put({
                    "error": str(exc),
                    "finished": True,
                    "crawl_progress": 1.0
                })

        task = asyncio.create_task(producer())
        _jobs[url] = {"task": task, "queue": queue}
        log.info("🚀 Audit Pipeline Initiated: %s", url)

    queue = _jobs[url]["queue"]

    async def event_stream():
        try:
            # immediate heartbeat improves perceived latency
            yield f"data: {_json({'crawl_progress': 0.0, 'status': 'Queued'})}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                with suppress(asyncio.TimeoutError):
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {_json(item)}\n\n"
                    if item.get("finished"):
                        break
        finally:
            # Optional: cleanup finished jobs to keep memory small
            task = _jobs[url]["task"]
            if task.done():
                _jobs.pop(url, None)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
