# app/audit/runner.py

import logging
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
    INPUT/OUTPUT unchanged.
    """

    settings = get_settings()
    logger.info(f"Auditing URL: {url}")

    # 1️⃣ Fetch PageSpeed Insights data
    psi_data = fetch_psi(url, api_key=settings.PSI_API_KEY)
    perf_score = 0
    lcp_ms = 4000  # default worst-case
    if psi_data and 'lighthouseResult' in psi_data:
        perf_category = psi_data['lighthouseResult']['categories']['performance']
        perf_score = perf_category.get('score', 0) * 100
        # Extract LCP (Largest Contentful Paint) if available
        audits = psi_data['lighthouseResult'].get('audits', {})
        lcp_ms = audits.get('largest-contentful-paint', {}).get('numericValue', 4000)

    # 2️⃣ Crawl the site to calculate coverage & broken links
    crawl_result = crawl(url, max_pages=50, timeout=10)
    total_pages = len(crawl_result.pages)
    total_broken_links = len(crawl_result.broken_internal) + len(crawl_result.broken_external)

    # 3️⃣ On-page SEO metrics (dummy for now, extendable later)
    onpage_metrics = {
        "missing_title_tags": 0,  # extend with actual parsing logic if needed
        "multiple_h1": 0
    }

    links_metrics = {
        "total_broken_links": total_broken_links
    }

    # 4️⃣ Compute final audit scores using grader
    overall_score, grade, breakdown = compute_scores(
        onpage=onpage_metrics,
        perf={"lcp_ms": lcp_ms},
        links=links_metrics,
        crawl_pages_count=total_pages
    )

    logger.info(f"Audit complete: URL={url}, Score={overall_score}, Grade={grade}, Pages={total_pages}")

    # 5️⃣ Return JSON output (matches frontend input/output exactly)
    return {
        "url": url,
        "overall_score": overall_score,
        "grade": grade,
        "breakdown": {
            "onpage": breakdown['onpage'],
            "performance": breakdown['performance'],
            "coverage": breakdown['coverage'],
            "confidence": breakdown['confidence']
        }
    }
