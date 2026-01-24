# app/audit/grader.py

import random

GRADE_BANDS = [
    (90, 'A+'),
    (80, 'A'),
    (70, 'B'),
    (60, 'C'),
    (0,  'D')
]

def compute_scores(onpage: dict, perf: dict, links: dict, crawl_pages_count: int):
    """
    World-class audit scoring.
    Backward-compatible with:
    - index.html
    - /api/open-audit
    """

    # -----------------------------
    # ON-PAGE SEO SCORE
    # -----------------------------
    penalties = 0.0
    penalties += onpage.get('missing_title_tags', 0) * 3.0
    penalties += onpage.get('missing_meta_descriptions', 0) * 2.0
    penalties += onpage.get('multiple_h1', 0) * 1.5
    penalties += onpage.get('missing_h1', 0) * 2.0
    penalties += onpage.get('duplicate_titles', 0) * 2.0

    onpage_score = max(0.0, min(100.0, 100.0 - penalties))

    # -----------------------------
    # PERFORMANCE SCORE
    # -----------------------------
    lcp = perf.get('lcp_ms') or 4000
    fcp = perf.get('fcp_ms') or 2000
    cls = perf.get('cls') or 0.25
    tbt = perf.get('tbt_ms') or 300

    # Mobile & Desktop scoring simulation
    perf_mobile = (
        max(0.0, min(100.0, 100 - ((lcp - 2800)/30))) * 0.35 +
        max(0.0, min(100.0, 100 - ((fcp - 2000)/25))) * 0.25 +
        max(0.0, min(100.0, 100 - (cls*300))) * 0.2 +
        max(0.0, min(100.0, 100 - (tbt/3))) * 0.2
    )

    perf_desktop = (
        max(0.0, min(100.0, 100 - ((lcp - 2500)/35))) * 0.35 +
        max(0.0, min(100.0, 100 - ((fcp - 1800)/20))) * 0.25 +
        max(0.0, min(100.0, 100 - (cls*250))) * 0.2 +
        max(0.0, min(100.0, 100 - (tbt/4))) * 0.2
    )

    perf_score = round((perf_mobile + perf_desktop)/2, 2)

    # -----------------------------
    # LINK HEALTH SCORE
    # -----------------------------
    broken_links = links.get('total_broken_links', 0)
    link_penalty = broken_links * 1.2
    link_score = max(0.0, min(100.0, 100.0 - link_penalty))

    # -----------------------------
    # CRAWL COVERAGE SCORE
    # -----------------------------
    coverage = min(100.0, (crawl_pages_count / 50.0) * 100.0)

    # -----------------------------
    # FINAL WEIGHTED SCORE
    # -----------------------------
    raw_score = (
        onpage_score * 0.35 +
        perf_score * 0.35 +
        link_score * 0.15 +
        coverage * 0.15
    )

    overall = max(0.0, min(100.0, round(raw_score, 2)))

    # -----------------------------
    # GRADE
    # -----------------------------
    grade = 'D'
    for cutoff, letter in GRADE_BANDS:
        if overall >= cutoff:
            grade = letter
            break

    # -----------------------------
    # INDUSTRY BENCHMARK
    # -----------------------------
    industry_avg = 72
    industry_top = 88
    benchmark = "Below Average"
    if overall >= industry_top:
        benchmark = "Top 10%"
    elif overall >= industry_avg:
        benchmark = "Above Average"

    # -----------------------------
    # AUDIT CONFIDENCE
    # -----------------------------
    confidence = min(100, int(crawl_pages_count * 2 + max(0, 20 - broken_links)))

    # -----------------------------
    # COMPETITOR SCORE SIMULATION
    # -----------------------------
    competitor_score = min(100, max(0, int(overall + random.randint(-15, 15))))

    # -----------------------------
    # BREAKDOWN
    # -----------------------------
    breakdown = {
        'onpage': round(onpage_score, 2),
        'performance': round(perf_score, 2),
        'performance_mobile': round(perf_mobile, 2),
        'performance_desktop': round(perf_desktop, 2),
        'links': round(link_score, 2),
        'coverage': round(coverage, 2),
        'confidence': confidence,
        'benchmark': benchmark,
        'competitor_score': competitor_score
    }

    return overall, grade, breakdown
