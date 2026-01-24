# app/audit/runner.py

import asyncio
import logging
from .crawler import crawl
from .performance import analyze_performance
from .grader import compute_scores

# Configure logging for Railway environment
logger = logging.getLogger("runner")
logger.setLevel(logging.INFO)

async def run_audit(url: str, max_pages: int = 50) -> dict:
    """
    Orchestrates the full audit process:
    1. Crawls the site using a thread pool to prevent blocking.
    2. Runs SEO analysis on the collected HTML.
    3. Triggers PageSpeed Insights (PSI) or fallback performance checks.
    4. Computes final scores and letter grades.
    """
    try:
        # 1. CRAWL PHASE
        # We use asyncio.to_thread because 'requests' in crawler.py is synchronous.
        # This prevents the whole server from freezing during the crawl.
        logger.info(f"🚀 Starting crawl for {url}")
        crawl_result = await asyncio.to_thread(crawl, url, max_pages)

        # 2. SEO ANALYSIS PHASE
        # Extracting real SEO data from the crawler's findings
        pages_count = len(crawl_result.pages)
        broken_internal = len(crawl_result.broken_internal)
        broken_external = len(crawl_result.broken_external)

        onpage = {
            'missing_title_tags': sum(
                1 for html in crawl_result.pages.values() if '<title>' not in html.lower()
            ),
            'multiple_h1': sum(
                1 for html in crawl_result.pages.values() if html.lower().count('<h1>') > 1
            ),
            'total_pages_scanned': pages_count
        }

        # 3. PERFORMANCE PHASE
        # analyze_performance handles the PSI API vs Fallback logic
        logger.info(f"⚡ Analyzing performance for {url}")
        perf = await asyncio.to_thread(analyze_performance, url)

        # 4. LINK SUMMARY
        links = {
            'total_broken_links': broken_internal + broken_external,
            'broken_internal': broken_internal,
            'broken_external': broken_external
        }

        # 5. SCORING PHASE
        # Final mathematical synthesis of all gathered data
        overall, grade, breakdown = compute_scores(onpage, perf, links, pages_count)

        # 6. RESULT PACKAGING
        # This structure is specifically designed for your index.html JavaScript
        result = {
            'url': url,
            'overall_score': overall,
            'grade': grade,
            'breakdown': breakdown,
            'details': {
                'onpage': onpage,
                'performance': perf,
                'links': links,
                'crawl_pages_count': pages_count,
            }
        }
        
        logger.info(f"✅ Audit completed for {url} with score {overall}")
        return result

    except Exception as e:
        logger.error(f"❌ Audit failed for {url}: {e}", exc_info=True)
        # Safe fallback so the frontend doesn't crash
        return {
            'url': url,
            'overall_score': 0,
            'grade': 'D',
            'breakdown': {'onpage': 0, 'performance': 0, 'coverage': 0, 'confidence': 0},
            'details': {}
        }
