# app/audit/runner.py
import asyncio
import logging
from .crawler import crawl
from .performance import analyze_performance
from .grader import compute_scores
from .links import analyze_links
from .seo import analyze_onpage

logger = logging.getLogger("audit_runner")

async def run_audit(url: str, max_pages: int = 15) -> dict:
    """
    Monolithic runner that isolates failures in individual modules.
    """
    try:
        # A. CRAWL & SEO (In parallel-ready thread)
        logger.info(f"Auditing: {url}")
        crawl_result = await asyncio.to_thread(crawl, url, max_pages)
        onpage = analyze_onpage(crawl_result.pages)
        
        # B. PERFORMANCE (Handles SSL Bypass)
        perf = await asyncio.to_thread(analyze_performance, url)
        
        # C. LINK ANALYSIS
        links = analyze_links(crawl_result)
        
        # D. GRADING
        overall, grade, breakdown = compute_scores(
            onpage, perf, links, len(crawl_result.pages)
        )

        # Final Payload
        return {
            "url": url,
            "overall_score": overall,
            "grade": grade,
            "breakdown": breakdown,
            "raw_metrics": {
                "onpage": onpage,
                "performance": perf,
                "links": links,
                "pages_scanned": len(crawl_result.pages)
            }
        }

    except Exception as e:
        logger.error(f"Runner failed for {url}: {e}")
        # SAFE FALLBACK: Ensures DB Insert doesn't fail
        return {
            "url": url,
            "overall_score": 0,
            "grade": "F",
            "breakdown": {"onpage": 0, "performance": 0, "coverage": 0, "confidence": 0},
            "error": str(e)
        }
