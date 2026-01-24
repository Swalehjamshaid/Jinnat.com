# app/audit/runner.py

import asyncio
import logging
from .crawler import crawl
from .performance import analyze_performance
from .grader import compute_scores

logger = logging.getLogger("runner")
logger.setLevel(logging.INFO)

async def run_audit(url: str, max_pages: int = 50) -> dict:
    """
    Full audit runner:
    1. Crawl the website
    2. Analyze performance
    3. Grade onpage, performance, coverage, broken links
    Returns a dict compatible with the frontend HTML UI.
    """
    try:
        # 1️⃣ Crawl website
        logger.info(f"Starting crawl for {url}")
        crawl_result = await asyncio.to_thread(crawl, url, max_pages)

        # 2️⃣ Extract on-page metrics
        pages_count = len(crawl_result.pages)
        broken_internal = len(crawl_result.broken_internal)
        broken_external = len(crawl_result.broken_external)
        # Dummy on-page SEO metrics
        onpage = {
            'missing_title_tags': sum(
                1 for html in crawl_result.pages.values() if '<title>' not in html.lower()
            ),
            'multiple_h1': sum(
                1 for html in crawl_result.pages.values() if html.lower().count('<h1>') > 1
            )
        }

        # 3️⃣ Performance analysis
        perf = analyze_performance(url)

        # 4️⃣ Link summary
        links = {
            'broken_internal': broken_internal,
            'broken_external': broken_external
        }

        # 5️⃣ Compute scores
        overall, grade, breakdown = compute_scores(onpage, perf, links, pages_count)

        # 6️⃣ Prepare result for frontend
        result = {
            'url': url,
            'overall_score': overall,
            'grade': grade,
            'breakdown': breakdown,
            'onpage': onpage,
            'performance': perf,
            'links': links,
            'crawl_pages_count': pages_count,
        }

        return result

    except Exception as e:
        logger.error(f"Audit failed for {url}: {e}", exc_info=True)
        return {
            'url': url,
            'overall_score': 0,
            'grade': 'D',
            'breakdown': {'onpage': 0, 'performance': 0, 'coverage': 0, 'confidence': 0},
            'onpage': {},
            'performance': {},
            'links': {},
            'crawl_pages_count': 0
        }
