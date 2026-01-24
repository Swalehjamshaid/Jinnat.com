# app/audit/runner.py
import asyncio
from typing import Any, Dict

from app.audit.grader import compute_scores

async def crawl_site(url: str, max_pages: int = 3, timeout_total_s: int = 20) -> Dict[str, Any]:
    """
    Python-native crawl stub.
    Returns a dictionary compatible with compute_scores:
    - pages: dict of URL -> HTML content
    - broken_internal: list of broken internal links
    - errors: number of fetch errors
    """
    await asyncio.sleep(1.0)  # simulate crawl delay

    # Create dict of URL -> HTML placeholder
    pages_dict = {f"{url}/page{i+1}": "<html></html>" for i in range(max_pages)}

    return {
        "pages": pages_dict,            # dict expected by compute_scores
        "broken_internal": [],          # no broken links in stub
        "errors": 0                     # no errors
    }

async def run_audit(url: str) -> Dict[str, Any]:
    """
    Run the full Python-native audit.
    - Crawl website (async)
    - Compute audit score locally (Python-only)
    """
    # Step 1: Crawl site
    crawl_result = await crawl_site(url=url, max_pages=3)

    # Step 2: Prepare crawl stats for grader
    crawl_stats = {
        "pages": crawl_result.get("pages", {}),          # dict
        "broken_links": crawl_result.get("broken_internal", []),
        "errors": crawl_result.get("errors", 0),
    }

    # Step 3: Compute audit score (Python-only)
    overall_score, grade, breakdown = compute_scores(
        lighthouse=None,  # no PSI/AI metrics
        crawl=crawl_stats
    )

    # Step 4: Return structured result
    result = {
        "overall_score": overall_score,
        "grade": grade,
        "breakdown": breakdown,
        "finished": True,
        "crawl_progress": 1.0
    }

    return result

# Test locally
if __name__ == "__main__":
    async def test():
        res = await run_audit("https://example.com")
        print(res)

    asyncio.run(test())
