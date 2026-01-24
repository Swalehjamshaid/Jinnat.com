# app/audit/runner.py

import logging
from ..settings import get_settings
from .psi import fetch_psi
from .crawler import crawl
from .grader import compute_scores

logger = logging.getLogger("audit_runner")

async def run_audit(url: str):
    """
    World-Class Audit Orchestrator:
    - Extracts 4 core Lighthouse categories.
    - Deep crawls for internal health.
    - Computes weighted scores for the Radar Dashboard.
    """

    settings = get_settings()
    logger.info(f"🚀 Initializing World-Class Audit for: {url}")

    # 1️⃣ Fetch Multi-Category PageSpeed Insights data
    # We now look for: Performance, SEO, Accessibility, and Best Practices
    psi_data = fetch_psi(url, api_key=settings.PSI_API_KEY)
    
    # Defaults
    lcp_ms = 4000
    scores = {
        "performance": 0,
        "seo": 0,
        "accessibility": 80,  # Fallback
        "best_practices": 80  # Fallback
    }

    if psi_data and 'lighthouseResult' in psi_data:
        lh = psi_data['lighthouseResult']
        categories = lh.get('categories', {})
        
        # Extract individual scores (multiplied by 100 for percentage)
        scores["performance"] = categories.get('performance', {}).get('score', 0) * 100
        scores["seo"] = categories.get('seo', {}).get('score', 0) * 100
        scores["accessibility"] = categories.get('accessibility', {}).get('score', 0) * 100
        scores["best_practices"] = categories.get('best-practices', {}).get('score', 0) * 100
        
        # Extract LCP (Largest Contentful Paint) for deep performance grading
        audits = lh.get('audits', {})
        lcp_ms = audits.get('largest-contentful-paint', {}).get('numericValue', 4000)

    # 2️⃣ Crawl the site (Coverage & Broken Link Detection)
    # This remains the heart of the 'Coverage' metric
    crawl_result = crawl(url, max_pages=50, timeout=10)
    
    pages_found = getattr(crawl_result, 'pages', [])
    total_pages = len(pages_found)
    
    broken_in = getattr(crawl_result, 'broken_internal', [])
    broken_ex = getattr(crawl_result, 'broken_external', [])
    total_broken_links = len(broken_in) + len(broken_ex)

    # 3️⃣ Prepare Data for the New Grader
    onpage_metrics = {
        "google_seo_score": scores["seo"],
        "missing_title_tags": 0, 
        "multiple_h1": 0
    }

    links_metrics = {
        "total_broken_links": total_broken_links,
        "total_pages_crawled": total_pages
    }
    
    extra_metrics = {
        "accessibility": scores["accessibility"],
        "best_practices": scores["best_practices"]
    }

    # 4️⃣ Compute Final Scores
    # Note: We now pass 'extra_metrics' to support the new World-Class Grader
    overall_score, grade, breakdown = compute_scores(
        onpage=onpage_metrics,
        perf={"lcp_ms": lcp_ms, "score": scores["performance"]},
        links=links_metrics,
        crawl_pages_count=total_pages,
        extra_metrics=extra_metrics
    )

    logger.info(f"✅ Audit Complete: Score={overall_score}, Grade={grade}")

    # 5️⃣ World-Class JSON Return
    return {
        "url": url,
        "overall_score": round(overall_score, 1),
        "grade": grade,
        "breakdown": {
            "onpage": round(breakdown.get('onpage', scores["seo"]), 1),
            "performance": round(breakdown.get('performance', scores["performance"]), 1),
            "coverage": round(breakdown.get('coverage', 0), 1),
            "confidence": round(breakdown.get('confidence', 95), 1),
            "accessibility": round(breakdown.get('accessibility', scores["accessibility"]), 1),
            "best_practices": round(breakdown.get('best_practices', scores["best_practices"]), 1)
        }
    }
