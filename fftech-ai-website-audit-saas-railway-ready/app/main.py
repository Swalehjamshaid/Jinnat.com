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

# In-memory job registry. For production use Redis/RQ/Celery.
_jobs: Dict[str, Dict[str, Any]] = {}

JOB_TTL_SECONDS = int(os.getenv("JOB_TTL_SECONDS", "900"))  # 15 minutes
SSE_HEARTBEAT_SECONDS = float(os.getenv("SSE_HEARTBEAT_SECONDS", "2.0"))


def json_dumps(obj) -> str:
    """Compact JSON for SSE."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def _job_key(url: str, api_key: str) -> str:
    return f"{url.strip()}|{api_key.strip()}"


def _cleanup_jobs() -> None:
    now = time.time()
    to_delete = []
    for k, v in _jobs.items():
        created_at = v.get("created_at", 0)
        task = v.get("task")
        if (now - created_at) > JOB_TTL_SECONDS:
            to_delete.append(k)
        elif task and task.done() and (now - created_at) > 60:
            to_delete.append(k)

    for k in to_delete:
        _jobs.pop(k, None)


async def run_audit_and_emit(url: str, api_key: str, queue: asyncio.Queue):
    async def emit(payload: Dict[str, Any]):
        payload["ts"] = time.time()
        await queue.put(payload)

    try:
        logger.info(f"Audit Started: {url}")
        await emit({"crawl_progress": 0.0, "psi_progress": 0.0, "status": "Starting Audit"})

        crawl_task = asyncio.create_task(crawl(url, max_pages=15))
        psi_task = asyncio.create_task(fetch_lighthouse(url, api_key))

        while not crawl_task.done() or not psi_task.done():
            await emit(
                {
                    "crawl_progress": 0.5 if not crawl_task.done() else 1.0,
                    "psi_progress": 0.5 if not psi_task.done() else 1.0,
                    "status": "Auditing...",
                }
            )
            await asyncio.sleep(SSE_HEARTBEAT_SECONDS)

        crawl_result, psi_result = await asyncio.gather(crawl_task, psi_task)

        crawl_stats = {
            "pages": len(getattr(crawl_result, "pages", []) or []),
            "broken_links": len(getattr(crawl_result, "broken_internal", []) or []),
            "errors": (getattr(crawl_result, "status_counts", {}) or {}).get(0, 0),
        }

        overall_score, grade, breakdown = compute_scores(
            lighthouse=psi_result,
            crawl=crawl_stats,
        )

        await emit(
            {
                "finished": True,
                "overall_score": overall_score,
                "grade": grade,
                "breakdown": breakdown,
                "crawl_progress": 1.0,
                "psi_progress": 1.0,
                "status": "Completed",
            }
        )

    except asyncio.CancelledError:
        await queue.put({"finished": True, "status": "Cancelled"})
        raise
    except Exception as exc:
        logger.exception(f"Audit failed for {url}")
        await queue.put(
            {
                "error": str(exc),
                "finished": True,
                "crawl_progress": 1.0,
                "psi_progress": 1.0,
                "status": "Failed",
            }
        )


# ✅ FIX: DO NOT hardcode /api here. main.py adds /api/v1 prefix.
@router.get("/open-audit-progress")
async def open_audit_progress(
    request: Request,
    url: str = Query(...),
    api_key: str = Query(...),
):
    _cleanup_jobs()
    key = _job_key(url, api_key)

    if key not in _jobs or _jobs[key]["task"].done():
        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(run_audit_and_emit(url, api_key, queue))
        _jobs[key] = {"task": task, "queue": queue, "created_at": time.time()}

    queue = _jobs[key]["queue"]
    task = _jobs[key]["task"]

    async def event_stream():
        yield f"data: {json_dumps({'crawl_progress': 0.0, 'psi_progress': 0.0, 'status': 'Queued'})}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    with suppress(Exception):
                        task.cancel()
                    break

                with suppress(asyncio.TimeoutError):
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json_dumps(item)}\n\n"
                    if item.get("finished"):
                        break
        finally:
            _cleanup_jobs()

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
