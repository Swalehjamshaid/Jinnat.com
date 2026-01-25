# app/audit/runner.py
import asyncio
from typing import Any, Dict

from app.audit.crawler import crawl
from app.audit.grader import compute_scores

async def run_audit(url: str) -> Dict[str, Any]:
    try:
        crawl_result = await crawl(url, max_pages=15)

        # convert CrawlResult to dict for grader
        crawl_stats = {
            "pages": crawl_result.pages,
            "broken_internal": crawl_result.broken_internal,
            "internal_links": crawl_result.internal_links,
            "external_links": crawl_result.external_links,
            "status_counts": crawl_result.status_counts,
            "errors": crawl_result.status_counts.get(0, 0),
        }

        overall_score, grade_letter, breakdown = compute_scores(
            lighthouse=None,
            crawl=crawl_stats
        )

        return {
            "finished": True,
            "overall_score": overall_score,
            "grade": grade_letter,
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
