# app/audit/runner.py
import asyncio
from app.audit.crawler import crawl
from app.audit.psi import fetch_lighthouse
from app.audit.grader import compute_scores

async def run_audit(url: str):
    """
    Run full audit using Python-only libraries.
    Crawl + local PSI simulation + grading.
    """
    crawl_result = await crawl(url, max_pages=15)
    crawl_stats = {
        "pages": len(crawl_result.pages),
        "broken_links": len(crawl_result.broken_internal),
        "errors": crawl_result.status_counts.get(0, 0),
    }

    psi_result = await fetch_lighthouse(url)

    overall_score, grade, breakdown = compute_scores(
        lighthouse=psi_result,
        crawl=crawl_stats
    )

    return {
        "finished": True,
        "overall_score": overall_score,
        "grade": grade,
        "breakdown": breakdown
    }
