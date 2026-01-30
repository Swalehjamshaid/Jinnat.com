# app/api/router.py
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import suppress
from typing import Dict, Any

from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse

from app.audit.crawler import crawl
from app.audit.psi import fetch_lighthouse
from app.audit.grader import compute_scores

logger = logging.getLogger("FFTech_Production")
logging.basicConfig(level=logging.INFO)

router = APIRouter()

# In-memory job registry (use Redis/Celery for multi-instance production).
_jobs: Dict[str, Dict[str, Any]] = {}

JOB_TTL_SECONDS = int(os.getenv("JOB_TTL_SECONDS", "900"))  # 15 minutes
SSE_PING_SECONDS = float(os.getenv("SSE_PING_SECONDS", "10.0"))  # ping interval
SSE_STATUS_SECONDS = float(os.getenv("SSE_STATUS_SECONDS", "2.0"))  # status updates


def json_dumps(obj: Any) -> str:
    """Compact JSON for SSE."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def _job_key(url: str, api_key: str) -> str:
    # Avoid collisions between different users (or different keys).
    return f"{url.strip()}|{api_key.strip()}"


def _cleanup_jobs() -> None:
    """Remove old finished jobs to prevent memory growth."""
    now = time.time()
    to_delete = []
    for k, v in list(_jobs.items()):
        created_at = v.get("created_at", 0.0)
        task = v.get("task")

        # TTL cleanup
        if (now - created_at) > JOB_TTL_SECONDS:
            to_delete.append(k)
            continue

        # Remove finished jobs older than 60 seconds
        if task and getattr(task, "done", lambda: False)():
            if (now - created_at) > 60:
                to_delete.append(k)

    for k in to_delete:
        _jobs.pop(k, None)


async def run_audit_and_emit(url: str, api_key: str, queue: asyncio.Queue) -> None:
    """Run crawl + lighthouse, compute scores, emit SSE updates via queue."""

    async def emit(payload: Dict[str, Any]) -> None:
        payload["ts"] = time.time()
        await queue.put(payload)

    try:
        logger.info("Audit Started: %s", url)
        await emit({"status": "Starting Audit", "crawl_progress": 0.0, "psi_progress": 0.0})

        crawl_task = asyncio.create_task(crawl(url, max_pages=15))
        psi_task = asyncio.create_task(fetch_lighthouse(url, api_key))

        # Periodically emit status while tasks run
        while not crawl_task.done() or not psi_task.done():
            await emit(
                {
                    "status": "Auditing...",
                    "crawl_progress": 0.5 if not crawl_task.done() else 1.0,
                    "psi_progress": 0.5 if not psi_task.done() else 1.0,
                }
            )
            await asyncio.sleep(SSE_STATUS_SECONDS)

        crawl_result, psi_result = await asyncio.gather(crawl_task, psi_task)

        crawl_stats = {
            "pages": len(getattr(crawl_result, "pages", []) or []),
            "broken_links": len(getattr(crawl_result, "broken_internal", []) or []),
            "errors": (getattr(crawl_result, "status_counts", {}) or {}).get(0, 0),
        }

        overall_score, grade, breakdown = compute_scores(lighthouse=psi_result, crawl=crawl_stats)

        await emit(
            {
                "finished": True,
                "status": "Completed",
                "overall_score": overall_score,
                "grade": grade,
                "breakdown": breakdown,
                "crawl_progress": 1.0,
                "psi_progress": 1.0,
            }
        )

    except asyncio.CancelledError:
        # Task cancelled due to client disconnect
        with suppress(Exception):
            await queue.put({"finished": True, "status": "Cancelled", "ts": time.time()})
        raise
    except Exception as exc:
        logger.exception("Audit failed for %s", url)
        await queue.put(
            {
                "error": str(exc),
                "finished": True,
                "status": "Failed",
                "crawl_progress": 1.0,
                "psi_progress": 1.0,
                "ts": time.time(),
            }
        )


@router.get("/open-audit-progress")
async def open_audit_progress(
    request: Request,
    url: str = Query(..., description="Target website URL"),
    api_key: str = Query(..., description="PSI/Lighthouse API key"),
):
    """
    SSE endpoint:
      - Starts audit if not already running
      - Streams progress + final result
    """
    _cleanup_jobs()
    key = _job_key(url, api_key)

    # Create job if missing or finished
    if key not in _jobs or _jobs[key]["task"].done():
        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(run_audit_and_emit(url, api_key, queue))
        _jobs[key] = {"task": task, "queue": queue, "created_at": time.time()}

    queue: asyncio.Queue = _jobs[key]["queue"]
    task: asyncio.Task = _jobs[key]["task"]

    async def event_stream():
        # Initial event
        yield f"data: {json_dumps({'status': 'Queued', 'crawl_progress': 0.0, 'psi_progress': 0.0})}\n\n"

        last_ping = time.time()

        try:
            while True:
                # Client disconnected? cancel work to save resources
                if await request.is_disconnected():
                    with suppress(Exception):
                        task.cancel()
                    break

                # Pull next message (or timeout)
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json_dumps(item)}\n\n"
                    if item.get("finished"):
                        break
                except asyncio.TimeoutError:
                    pass

                # Heartbeat ping to prevent proxy idle timeouts
                now = time.time()
                if (now - last_ping) >= SSE_PING_SECONDS:
                    # SSE comment line (doesn't affect client parsing)
                    yield ": ping\n\n"
                    last_ping = now

        finally:
            _cleanup_jobs()

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # important for nginx/proxy buffering
    }

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
