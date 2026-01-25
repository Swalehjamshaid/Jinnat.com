# app/audit/runner.py

import asyncio
from typing import Any, Dict

from app.audit.crawler import crawl
from app.audit.grader import compute_scores
from app.audit.links import analyze_links
from app.audit.performance import analyze_performance
from app.audit.seo import analyze_onpage

async def run_audit(url: str) -> Dict[str, Any]:
    """
    Full Python-native audit:
    - Crawl the website
    - Analyze links, performance, SEO
    - Compute overall scores using compute_scores
    - Returns overall_score, grade, breakdown, and detailed metrics
    """
    try:
        # --- Crawl the website ---
        crawl_result = await crawl(url, max_pages=15)

        # --- Analyze Links ---
        link_metrics = analyze_links(crawl_result)

        # --- Analyze Performance ---
        perf_metrics = analyze_performance(url)

        # --- Analyze SEO ---
        seo_metrics = analyze_onpage(crawl_result.pages)

        # --- Prepare stats for grader ---
        crawl_stats = {
            "pages": crawl_result.pages,  # dict: {url: html}
            "broken_links": link_metrics["total_broken_links"],
            "errors": crawl_result.status_counts.get(0, 0),
            "internal_links": crawl_result.internal_links,
            "external_links": crawl_result.external_links,
        }

        # --- Compute overall scores ---
        overall_score, grade, breakdown = compute_scores(
            lighthouse=None,  # Python-only, no PSI
            crawl=crawl_stats
        )

        return {
            "finished": True,
            "overall_score": overall_score,
            "grade": grade,
            "breakdown": breakdown,
            "links": link_metrics,
            "performance": perf_metrics,
            "seo": seo_metrics,
            "crawl_progress": 1.0
        }

    except Exception as e:
        return {
            "finished": True,
            "error": str(e),
            "overall_score": 0,
            "grade": "F",
            "breakdown": {},
            "links": {},
            "performance": {},
            "seo": {},
            "crawl_progress": 0
        }
