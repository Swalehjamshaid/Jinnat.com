# app/audit/runner.py
import asyncio
import logging
from .psi import fetch_psi
from .crawler import crawl
from .grader import compute_scores
from ..settings import get_settings

logger = logging.getLogger("audit_runner")

async def run_audit(url: str):
    settings = get_settings()
    logger.info(f"🚀 Starting Concurrent Audit for: {url}")
    
    # SPEED FIX: Run PSI and Crawler in PARALLEL
    # We reduce max_pages to 10 for "SaaS Fast-Track" speed
    psi_task = asyncio.to_thread(fetch_psi, url, api_key=settings.PSI_API_KEY)
    crawl_task = asyncio.to_thread(crawl, url, max_pages=10, timeout=7)

    # Wait for both to finish simultaneously
    psi_data, crawl_result = await asyncio.gather(psi_task, crawl_task)

    # Extract PageSpeed Metrics
    scores = {"perf": 0, "seo": 0, "acc": 80, "bp": 80}
    if psi_data and 'lighthouseResult' in psi_data:
        cats = psi_data['lighthouseResult'].get('categories', {})
        scores["perf"] = cats.get('performance', {}).get('score', 0) * 100
        scores["seo"] = cats.get('seo', {}).get('score', 0) * 100
        scores["acc"] = cats.get('accessibility', {}).get('score', 0) * 100
        scores["bp"] = cats.get('best-practices', {}).get('score', 0) * 100

    pages_found = len(getattr(crawl_result, 'pages', {}))
    
    # Call the FIXED Grader
    overall_score, grade, breakdown = compute_scores(
        onpage={"google_seo_score": scores["seo"]},
        perf={"score": scores["perf"]},
        links={"total_broken_links": 0},
        crawl_pages_count=pages_found,
        extra_metrics={
            "accessibility": scores["acc"],
            "best_practices": scores["bp"]
        }
    )

    return {
        "overall_score": overall_score,
        "grade": grade,
        "breakdown": breakdown
    }
