# app/api/routes.py
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
import asyncio
from typing import Dict, Any
from contextlib import suppress
import json
import logging

from app.audit.crawler import crawl
from app.audit.psi import fetch_lighthouse
from app.audit.grader import compute_scores

logger = logging.getLogger("FFTech_Production")
logging.basicConfig(level=logging.INFO)

router = APIRouter()

# In-memory job registry. For production, prefer Redis or RQ
_jobs: Dict[str, Dict[str, Any]] = {}

def json_dumps(obj) -> str:
    """Compact JSON for SSE."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


async def run_audit_and_emit(url: str, api_key: str, queue: asyncio.Queue):
    """
    Run the audit for a URL:
      - Crawl pages
      - Fetch Lighthouse metrics (async)
      - Compute final scores
      - Emit progress updates via queue
    """
    async def emit_progress(crawl_pct: float = None, psi_pct: float = None, status: str = None):
        payload = {}
        if crawl_pct is not None:
            payload["crawl_progress"] = crawl_pct
        if psi_pct is not None:
            payload["psi_progress"] = psi_pct
        if status:
            payload["status"] = status
        await queue.put(payload)

    try:
        logger.info(f"Audit Started: {url}")
        await emit_progress(0.0, 0.0, "Starting Audit")

        # -----------------------------
        # Start async crawl and Lighthouse fetch concurrently
        # -----------------------------
        crawl_task = asyncio.create_task(crawl(url, max_pages=15))
        psi_task = asyncio.create_task(fetch_lighthouse(url, api_key))

        # While tasks run, we can emit incremental updates (fake loop for demo)
        while not crawl_task.done() or not psi_task.done():
            crawl_pct = 0.0
            psi_pct = 0.0
            if crawl_task.done():
                crawl_pct = 1.0
            else:
                crawl_pct = 0.5  # or crawl_task.progress() if implemented

            if psi_task.done():
                psi_pct = 1.0
            else:
                psi_pct = 0.5

            await emit_progress(crawl_pct, psi_pct, "Auditing...")
            await asyncio.sleep(0.5)

        # Wait for results
        crawl_result, psi_result = await asyncio.gather(crawl_task, psi_task)

        # -----------------------------
        # Compute scores
        # -----------------------------
        crawl_stats = {
            "pages": len(crawl_result.pages),
            "broken_links": len(crawl_result.broken_internal),
            "errors": crawl_result.status_counts.get(0, 0),
        }

        overall_score, grade, breakdown = compute_scores(
            lighthouse=psi_result,
            crawl=crawl_stats
        )

        final_payload = {
            "finished": True,
            "overall_score": overall_score,
            "grade": grade,
            "breakdown": breakdown,
            "crawl_progress": 1.0,
            "psi_progress": 1.0
        }

        await queue.put(final_payload)

    except Exception as exc:
        logger.exception(f"Audit failed for {url}")
        await queue.put({
            "error": str(exc),
            "finished": True,
            "crawl_progress": 1.0,
            "psi_progress": 1.0
        })


@router.get("/api/open-audit-progress")
async def open_audit_progress(request: Request, url: str = Query(...), api_key: str = Query(...)):
    """
    SSE endpoint for audit progress.
      - Starts audit if not already running
      - Streams progress + final result
    """
    # Start new job if none exists or previous finished
    if url not in _jobs or _jobs[url]["task"].done():
        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(run_audit_and_emit(url, api_key, queue))
        _jobs[url] = {"task": task, "queue": queue}

    queue = _jobs[url]["queue"]
    task = _jobs[url]["task"]

    async def event_stream():
        try:
            # Initial heartbeat
            yield f"data: {json_dumps({'crawl_progress': 0.0, 'psi_progress': 0.0, 'status': 'Queued'})}\n\n"
            while True:
                if await request.is_disconnected():
                    break

                with suppress(asyncio.TimeoutError):
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json_dumps(item)}\n\n"
                    if item.get("finished"):
                        break
        finally:
            # Optional cleanup: keep last job for cache
            if task.done():
                # _jobs.pop(url, None)  # Uncomment to remove finished jobs
                pass

    return StreamingResponse(event_stream(), media_type="text/event-stream")
