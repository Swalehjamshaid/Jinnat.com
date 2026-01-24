# app/audit/runner.py

import logging
import asyncio # Added for better handling if needed
from ..settings import get_settings
from .psi import fetch_psi
from .crawler import crawl
from .grader import compute_scores

logger = logging.getLogger("audit_runner")

async def run_audit(url: str):
    """
    Run a complete website audit for the given URL:
    - PageSpeed Insights for performance
    - Crawl for coverage and link checks
    - Grader for final scoring
    """

    settings = get_settings()
    logger.info(f"Auditing URL: {url}")

    # 1️⃣ Fetch PageSpeed Insights data
    # Note: Ensure fetch_psi is handled properly as it might be a sync call in your current setup
    psi_data = fetch_psi(url, api_key=settings.PSI_API_KEY)
    
    perf_score = 0
    lcp_ms = 4000  # default worst-case
    seo_score = 0
    
    if psi_data and 'lighthouseResult' in psi_data:
        lh = psi_data['lighthouseResult']
        categories = lh.get('categories', {})
        
        # Get Performance
        perf_category = categories.get('performance', {})
        perf_score = perf_category.get('score', 0) * 100
        
        # Get SEO score from Google to help with 'onpage' breakdown
        seo_category = categories.get('seo', {})
        seo_score = seo_category.get('score', 0) * 100
        
        # Extract LCP (Largest Contentful Paint)
        audits = lh.get('audits', {})
        lcp_ms = audits.get('largest-contentful-paint', {}).get('numericValue', 4000)

    # 2️⃣ Crawl the site to calculate coverage & broken links
    # Max pages set to 50; this dictates the 'Coverage' potential
    crawl_result = crawl(url, max_pages=50, timeout=10)
    
    # FIX: Ensure we are counting pages correctly
    pages_found = getattr(crawl_result, 'pages', [])
    total_pages = len(pages_found)
    
    broken_in = getattr(crawl_result, 'broken_internal', [])
    broken_ex = getattr(crawl_result, 'broken_external', [])
    total_broken_links = len(broken_in) + len(broken_ex)

    # 3️⃣ Prepare metrics for the grader
    # We pass the seo_score from Google to make 'onpage' accurate
    onpage_metrics = {
        "google_seo_score": seo_score,
        "missing_title_tags": 0, 
        "multiple_h1": 0
    }

    links_metrics = {
        "total_broken_links": total_broken_links,
        "total_pages_crawled": total_pages
    }

    # 4️⃣ Compute final audit scores using grader
    # The grader uses 'crawl_pages_count' to determine Coverage %
    overall_score, grade, breakdown = compute_scores(
        onpage=onpage_metrics,
        perf={"lcp_ms": lcp_ms, "score": perf_score},
        links=links_metrics,
        crawl_pages_count=total_pages
    )

    logger.info(f"Audit complete: URL={url}, Score={overall_score}, Grade={grade}, Pages={total_pages}")

    # 5️⃣ Return JSON output (matches frontend index.html exactly)
    return {
        "url": url,
        "overall_score": round(overall_score, 1),
        "grade": grade,
        "breakdown": {
            "onpage": round(breakdown.get('onpage', seo_score), 1),
            "performance": round(breakdown.get('performance', perf_score), 1),
            "coverage": round(breakdown.get('coverage', 0), 1),
            "confidence": round(breakdown.get('confidence', 90), 1)
        }
    }
