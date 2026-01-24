# app/grader.py

GRADE_BANDS = [
    (90, 'A+'),
    (80, 'A'),
    (70, 'B'),
    (60, 'C'),
    (0, 'D')
]

def compute_scores(onpage: dict, perf: dict, links: dict, crawl_pages_count: int):
    """
    Computes overall audit scores with international standards, including:
    - Onpage SEO checks
    - Performance (LCP, FCP)
    - Coverage based on crawl pages
    - Broken links penalty
    - Mobile vs Desktop scoring
    - Audit confidence
    - Competitor simulation
    - Industry benchmark
    """

    # -------------------------
    # Penalties based on on-page issues
    # -------------------------
    penalties = 0
    penalties += onpage.get('missing_title_tags', 0) * 2
    penalties += onpage.get('missing_meta_descriptions', 0) * 1.5
    penalties += onpage.get('multiple_h1', 0) * 1
    penalties += links.get('total_broken_links', 0) * 0.5

    # -------------------------
    # Performance scoring
    # -------------------------
    lcp = perf.get('lcp_ms', 4000) or 4000
    fcp = perf.get('fcp_ms', 2000) or 2000
    perf_score = max(0, 100 - (lcp / 40 + fcp / 30))

    # -------------------------
    # Coverage based on pages crawled
    # -------------------------
    coverage = min(100, crawl_pages_count * 2)

    # -------------------------
    # Weighted overall score
    # -------------------------
    # Onpage 50%, Performance 30%, Coverage 20%
    raw_score = max(0, 100 - penalties) * 0.5 + perf_score * 0.3 + coverage * 0.2
    overall = max(0, min(100, raw_score))

    # -------------------------
    # Determine letter grade
    # -------------------------
    grade = 'D'
    for cutoff, letter in GRADE_BANDS:
        if overall >= cutoff:
            grade = letter
            break

    # -------------------------
    # Mobile/Desktop scores
    # -------------------------
    mobile_score = perf.get('mobile_score', perf_score)
    desktop_score = perf.get('desktop_score', perf_score)

    # -------------------------
    # Audit confidence & competitor simulation
    # -------------------------
    confidence = min(100, max(50, 100 - penalties / 2))  # % confidence
    competitor_score = max(0, min(100, overall - 5))  # Simulated competitor score
    benchmark = 85  # Industry benchmark (example)

    # -------------------------
    # Return structured breakdown
    # -------------------------
    breakdown = {
        "onpage": max(0, 100 - penalties),
        "performance": perf_score,
        "coverage": coverage,
        "performance_mobile": mobile_score,
        "performance_desktop": desktop_score,
        "confidence": confidence,
        "competitor_score": competitor_score,
        "benchmark": benchmark,
        "links": max(0, 100 - links.get('total_broken_links', 0) * 5)
    }

    return overall, grade, breakdown
