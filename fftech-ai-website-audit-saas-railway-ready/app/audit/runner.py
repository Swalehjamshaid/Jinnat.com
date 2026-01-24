# app/audit/runner.py
import asyncio
from typing import Any, Dict

from app.audit.crawler import crawl
from app.audit.grader import compute_scores

async def run_audit(url: str) -> Dict[str, Any]:
    """
    Full Python-native audit:
    - Crawl the website
    - Compute scores using compute_scores
    - Returns overall_score, grade, breakdown
    """
    try:
        # Run crawl (Python-native)
        crawl_result = await crawl(url, max_pages=15)

        # --- Prepare crawl stats for grader ---
        # compute_scores expects 'pages' as dict and broken_links as int
        crawl_stats = {
            "pages": crawl_result.pages,  # dict: {url: html}
            "broken_links": len(crawl_result.broken_internal),
            "errors": crawl_result.status_counts.get(0, 0),
        }

        # --- Compute scores ---
        overall_score, grade, breakdown = compute_scores(
            lighthouse=None,  # Python-only, no PSI
            crawl=crawl_stats
        )

        return {
            "finished": True,
            "overall_score": overall_score,
            "grade": grade,
            "breakdown": breakdown,
            "crawl_progress": 1.0
        }

    except Exception as e:
        return {
            "finished": True,
            "error": str(e),
            "overall_score": 0,
            "grade": "F",
            "breakdown": {},
            "crawl_progress": 0
        }
