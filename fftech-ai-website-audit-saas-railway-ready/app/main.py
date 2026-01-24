
# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
from contextlib import suppress
from typing import Dict, Any
import json
import logging
import time

from app.audit.runner import run_audit  # your existing function

log = logging.getLogger("FFTech_AI_Auditor")

app = FastAPI()

_jobs: Dict[str, Dict[str, Any]] = {}

def _json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)

@app.post("/api/open-audit")
async def compat_open_audit(request: Request):
    """
    Compat endpoint (front-end may POST here).
    No-op because SSE starts the job. Return 202 to avoid 404 noise.
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
    # Start a job if none exists or last one is done
    if url not in _jobs or _jobs[url]["task"].done():
        queue: asyncio.Queue = asyncio.Queue()

        async def producer():
            try:
                # Emit staged status before the heavy call
                await queue.put({"crawl_progress": 0.05, "status": "Initializing"})
                # IMPORTANT: run_audit must be non-blocking or run in a thread pool
                result = await run_audit(url)
                # run_audit should return a dict with finished=True and crawl_progress=1.0
                # If it doesn't, we enforce finish semantics:
                if not result.get("finished"):
                    result["finished"] = True
                if "crawl_progress" not in result:
                    result["crawl_progress"] = 1.0
                await queue.put(result)
            except Exception as exc:
                log.exception("❌ Critical Failure while auditing %s: %s", url, exc)
                await queue.put({
                    "error": str(exc),
                    "finished": True,
                    "crawl_progress": 1.0
                })

        task = asyncio.create_task(producer())
        _jobs[url] = {"task": task, "queue": queue, "ts": time.time()}
        log.info("🚀 Audit Pipeline Initiated: %s", url)
    else:
        # refresh last access time
        _jobs[url]["ts"] = time.time()

    queue = _jobs[url]["queue"]
    task = _jobs[url]["task"]

    async def event_stream():
        last_heartbeat = time.time()
        heartbeat_interval = 1.0  # seconds
        try:
            # immediate heartbeat improves perceived latency
            yield f"data: {_json({'crawl_progress': 0.0, 'status': 'Queued'})}\n\n"

            while True:
                if await request.is_disconnected():
                    break

                # Try to get the next queue item with timeout for heartbeat
                item = None
                with suppress(asyncio.TimeoutError):
                    item = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)

                now = time.time()
                if item is not None:
                    yield f"data: {_json(item)}\n\n"
                    last_heartbeat = now
                    if item.get("finished"):
                        break
                else:
                    # no item this second ⇒ send heartbeat to keep the pipe open
                    yield f"data: {_json({'heartbeat': True})}\n\n"

        finally:
            # Optional cleanup to prevent memory growth
            if task.done():
                _jobs.pop(url, None)

    # Add headers to discourage proxy buffering
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        # Optional (some proxies honor this): "Connection": "keep-alive"
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
