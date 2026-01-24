# app/audit/runner.py
import asyncio
from typing import Any, Dict

from app.audit.crawler import crawl  # Python-native crawler
from app.audit.psi import python_library_audit  # Python-native "pre-audit"
from app.audit.grader import compute_scores  # grading logic

async def run_audit(url: str) -> Dict[str, Any]:
    """
    Run the full audit using only Python libraries:
    - Crawl the site (async)
    - Run Python audit on the URL (performance, SEO, accessibility, etc.)
    - Compute overall score & grade using grader.py
    """

    # --- Run crawler and Python audit concurrently ---
    crawl_task = crawl(url, max_pages=10)  # async crawler
    audit_task = asyncio.to_thread(python_library_audit, url)  # run sync audit in thread

    crawl_result, audit_result = await asyncio.gather(crawl_task, audit_task, return_exceptions=True)

    # --- Default placeholders ---
    overall_score = 0
    grade = "F"
    breakdown = {}

    # --- Extract crawl metrics safely ---
    if not isinstance(crawl_result, Exception):
        crawl_stats = {
            "pages": len(getattr(crawl_result, "pages", [])),
            "broken_links": len(getattr(crawl_result, "broken_internal", [])),
            "errors": crawl_result.status_counts.get(0, 0) if hasattr(crawl_result, "status_counts") else 0,
        }
    else:
        crawl_stats = {"pages": 0, "broken_links": 0, "errors": 0}

    # --- Compute audit scores using grader ---
    if not isinstance(audit_result, Exception):
        overall_score, grade, breakdown = compute_scores(
            lighthouse=audit_result,
            crawl=crawl_stats
        )

    # --- Build result object ---
    result: Dict[str, Any] = {
        "overall_score": overall_score,
        "grade": grade,
        "breakdown": breakdown,
        "finished": True,
        "crawl_progress": 1.0,
    }

    # Optional: attach debug info if exceptions occurred
    if isinstance(crawl_result, Exception):
        result["crawl_error"] = str(crawl_result)
    if isinstance(audit_result, Exception):
        result["audit_error"] = str(audit_result)

    return result
