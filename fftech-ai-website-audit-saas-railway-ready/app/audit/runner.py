import asyncio
from typing import Any, Dict

from app.audit.crawler import crawl
from app.audit.grader import compute_scores
from app.audit.links import analyze_links
from app.audit.seo import analyze_onpage
from app.audit.performance import analyze_performance

async def run_audit(url: str) -> Dict[str, Any]:
    """
    Full Python-native audit:
    - Crawl the website
    - Analyze links, SEO, performance
    - Compute scores using grader
    - Returns overall_score, grade, breakdown
    """
    try:
        # Step 1: Crawl the website
        crawl_result = await crawl(url, max_pages=15)

        # Step 2: Analyze links
        link_stats = analyze_links(crawl_result)

        # Step 3: Analyze SEO
        seo_metrics = analyze_onpage(crawl_result.pages)

        # Step 4: Analyze Performance
        performance_metrics = analyze_performance(url)

        # Step 5: Prepare stats for grading
        crawl_stats = {
            "pages": crawl_result.pages,
            "broken_links": link_stats.get("total_broken_links", 0),
            "errors": crawl_result.status_counts.get(0, 0),
            "internal_links": crawl_result.internal_links
        }

        # Step 6: Compute overall scores
        overall_score, grade_letter, breakdown = compute_scores(
            lighthouse=None,
            crawl=crawl_stats
        )

        # Step 7: Include SEO & Performance in breakdown
        breakdown.update({
            "seo_details": seo_metrics,
            "performance": performance_metrics,
        })

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
