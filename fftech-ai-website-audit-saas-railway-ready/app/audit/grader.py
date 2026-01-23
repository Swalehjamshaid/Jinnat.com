# app/audit/grader.py

GRADE_BANDS = [(90,'A+'), (80,'A'), (70,'B'), (60,'C'), (0,'D')]

def compute_scores(onpage: dict, perf: dict, links: dict, crawl_pages_count: int):
    penalties = 0
    penalties += onpage.get('missing_title_tags', 0) * 2
    penalties += onpage.get('missing_meta_descriptions', 0) * 1.5
    penalties += onpage.get('multiple_h1', 0) * 1
    penalties += links.get('total_broken_links', 0) * 0.5

    lcp = perf.get('lcp_ms', 4000) or 4000
    fcp = perf.get('fcp_ms', 2000) or 2000
    perf_score = max(0, 100 - (lcp/40 + fcp/30))

    coverage = min(100, crawl_pages_count * 2)
    raw = max(0, 100 - penalties) * 0.5 + perf_score * 0.3 + coverage * 0.2
    overall = max(0, min(100, raw))

    grade = 'D'
    for cutoff, letter in GRADE_BANDS:
        if overall >= cutoff:
            grade = letter
            break

    return overall, grade, {
        'onpage': max(0, 100 - penalties),
        'performance': perf_score,
        'coverage': coverage
    }

# --------------------------
# Add run_audit here
# --------------------------

def run_audit(url: str):
    """
    Run a website audit for a given URL.
    This is a basic placeholder. Replace with actual crawl/performance logic.
    """
    # Example placeholder data — replace with your real crawler or AIService integration
    onpage = {
        "missing_title_tags": 1,
        "missing_meta_descriptions": 2,
        "multiple_h1": 0
    }
    perf = {
        "lcp_ms": 3500,
        "fcp_ms": 1800
    }
    links = {
        "total_broken_links": 3
    }
    crawl_pages_count = 15  # example number of pages crawled

    overall, grade, breakdown = compute_scores(onpage, perf, links, crawl_pages_count)

    return {
        "url": url,
        "overall_score": overall,
        "grade": grade,
        "breakdown": breakdown
    }
