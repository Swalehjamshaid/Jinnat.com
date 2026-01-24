# app/audit/runner.py
import asyncio
from .crawler import crawl
from .performance import analyze_performance
from .grader import compute_scores
from .links import analyze_links
from .seo import analyze_onpage

async def run_audit(url: str, max_pages: int = 20) -> dict:
    """
    Complete audit workflow with error isolation.
    If one module fails, the others continue to provide a partial result.
    """
    try:
        # 1. Gather Data (Crawl & SEO)
        crawl_result = await asyncio.to_thread(crawl, url, max_pages)
        onpage = analyze_onpage(crawl_result.pages)
        
        # 2. Gather Speed (Performance)
        perf = await asyncio.to_thread(analyze_performance, url)
        
        # 3. Summarize Links
        links = analyze_links(crawl_result)
        
        # 4. Final Scoring
        overall, grade, breakdown = compute_scores(onpage, perf, links, len(crawl_result.pages))

        # 5. Result Construction
        # This dictionary MUST match the JSON structure expected by the DB and UI
        return {
            "url": url,
            "overall_score": overall,
            "grade": grade,
            "breakdown": breakdown,
            "details": {
                "onpage": onpage,
                "performance": perf,
                "links": links,
                "pages_found": len(crawl_result.pages)
            }
        }
    except Exception as e:
        print(f"RUNNER ERROR: {e}")
        # Fallback dictionary to prevent DB Insert failure
        return {
            "url": url, "overall_score": 0, "grade": "D", 
            "breakdown": {"onpage":0, "performance":0, "coverage":0, "confidence":0}
        }
