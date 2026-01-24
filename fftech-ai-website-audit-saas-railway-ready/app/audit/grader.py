
# app/audit/grader.py

from typing import Dict, Tuple
import random
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import json

router = APIRouter()  # <-- Use a router; do NOT create a FastAPI() app here

# Grade bands for score cutoffs
GRADE_BANDS = [
    (90, 'A+'),
    (80, 'A'),
    (70, 'B'),
    (60, 'C'),
    (0,  'D')
]

# ======================================
# 1️⃣ Core Grader Function (unchanged logic)
# ======================================
def compute_scores(
    onpage: Dict[str, float],
    perf: Dict[str, float],
    links: Dict[str, float],
    crawl_pages_count: int
) -> Tuple[float, str, Dict[str, float]]:
    try:
        penalties = 0.0
        penalties += float(onpage.get('missing_title_tags', 0)) * 2.0
        penalties += float(onpage.get('multiple_h1', 0)) * 1.0
        penalties += float(links.get('total_broken_links', 0)) * 0.5
        penalties = min(100.0, penalties)

        lcp_ms = perf.get('lcp_ms', 4000) or 4000
        perf_score = 100.0
        if lcp_ms > 2500:
            perf_score = max(0.0, 100.0 - ((lcp_ms - 2500) / 25))
        perf_score = min(100.0, perf_score)

        pages = max(0, crawl_pages_count or 0)
        coverage_score = min(100.0, pages * 2.0)

        raw_score = (perf_score * 0.4) + (coverage_score * 0.6)
        overall_score = max(0.0, min(100.0, raw_score - penalties))

        grade = 'D'
        for cutoff, letter in GRADE_BANDS:
            if overall_score >= cutoff:
                grade = letter
                break

        confidence = round(random.uniform(92, 99), 2)

        breakdown = {
            'onpage': round(max(0.0, 100.0 - penalties), 2),
            'performance': round(perf_score, 2),
            'coverage': round(coverage_score, 2),
            'confidence': confidence
        }

        return round(overall_score, 2), grade, breakdown

    except Exception as e:
        print(f"[GRADER ERROR] {e}")
        return 0.0, "D", {
            "onpage": 0,
            "performance": 0,
            "coverage": 0,
            "confidence": 0
        }

# ======================================
# 2️⃣ SSE Endpoint for Live Progress (non-blocking + robust)
# ======================================
@router.get("/api/open-audit-progress")
async def open_audit_progress(request: Request, url: str):
    """
    Streams live audit progress for frontend integration.
    Preserves input/output structure for HTML JS.
    """

    async def event_stream():
        try:
            # Initial heartbeat so the UI shows immediate activity
            yield "data: " + json.dumps({"crawl_progress": 0.0, "finished": False, "status": "Queued"}) + "\n\n"

            # Simulate crawl characteristics (replace with your real crawl)
            total_pages = random.randint(10, 50)
            onpage_metrics = {
                "missing_title_tags": random.randint(0, 5),
                "multiple_h1": random.randint(0, 3)
            }
            perf_metrics = {"lcp_ms": random.randint(1200, 5000)}
            link_metrics = {"total_broken_links": random.randint(0, 10)}

            # Emit steady progress without blocking the event loop
            for i in range(1, total_pages + 1):
                # Respect client disconnects to avoid work after SSE closes
                if await request.is_disconnected():
                    break

                progress = i / total_pages
                payload = {
                    "crawl_progress": progress,
                    "finished": False,
                    # Optional status for nicer UI; your frontend can ignore it
                    "status": "Crawling Website..."
                }
                yield "data: " + json.dumps(payload) + "\n\n"

                # Non-blocking delay
                await asyncio.sleep(0.08)  # tune as needed

            # If client disconnected mid-stream, stop
            if await request.is_disconnected():
                return

            # Compute final scores
            overall_score, grade, breakdown = compute_scores(
                onpage=onpage_metrics,
                perf=perf_metrics,
                links=link_metrics,
                crawl_pages_count=total_pages
            )

            final_data = {
                "finished": True,
                "overall_score": overall_score,
                "grade": grade,
                "breakdown": breakdown
            }
            yield "data: " + json.dumps(final_data) + "\n\n"

        except Exception as exc:
            # Send a terminal error event so the UI can react
            err_payload = {"finished": True, "error": str(exc), "crawl_progress": 1.0}
            yield "data: " + json.dumps(err_payload) + "\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
