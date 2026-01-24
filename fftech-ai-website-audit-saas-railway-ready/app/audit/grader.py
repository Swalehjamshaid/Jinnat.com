# app/grader.py
"""
World-class Website Audit Grader
Compatible with FF Tech AI Website Audit SaaS
"""

import math

# Standard grading bands
GRADE_BANDS = [
    (90, 'A+'),
    (80, 'A'),
    (70, 'B'),
    (60, 'C'),
    (0, 'D')
]

def compute_scores(onpage: dict, perf: dict, links: dict, crawl_pages_count: int, competitors: dict = None):
    """
    Compute audit scores for a website based on multiple factors.
    Returns overall score, letter grade, and detailed breakdown.
    
    Parameters:
        onpage (dict): On-page SEO issues (missing titles, meta descriptions, h1 tags)
        perf (dict): Performance metrics {'lcp_ms': int, 'fcp_ms': int, 'mobile_score': int, 'desktop_score': int}
        links (dict): Link metrics {'total_broken_links': int, 'total_links': int}
        crawl_pages_count (int): Number of pages crawled
        competitors (dict): Optional competitor scores {'competitor_name': score}
        
    Returns:
        overall (float): Overall audit score (0-100)
        grade (str): Letter grade
        breakdown (dict): Detailed score breakdown
    """
    
    # --------------------------
    # Penalties for SEO issues
    # --------------------------
    penalties = 0
    penalties += onpage.get('missing_title_tags', 0) * 2
    penalties += onpage.get('missing_meta_descriptions', 0) * 1.5
    penalties += onpage.get('multiple_h1', 0) * 1

    # --------------------------
    # Link integrity score
    # --------------------------
    total_links = links.get('total_links', 1) or 1
    broken_links = links.get('total_broken_links', 0)
    link_penalty_ratio = broken_links / total_links
    link_score = max(0, 100 - link_penalty_ratio * 50)  # Broken links reduce score up to 50 points

    # --------------------------
    # Performance scoring (mobile & desktop)
    # --------------------------
    lcp = perf.get('lcp_ms', 4000) or 4000
    fcp = perf.get('fcp_ms', 2000) or 2000

    perf_score = max(0, 100 - (lcp / 40 + fcp / 30))  # simple linear penalty

    # Mobile vs Desktop weighting
    mobile_score = perf.get('mobile_score', perf_score)
    desktop_score = perf.get('desktop_score', perf_score)
    perf_weighted = (mobile_score * 0.6 + desktop_score * 0.4)

    # --------------------------
    # Crawl coverage
    # --------------------------
    coverage = min(100, crawl_pages_count * 2)  # Each page adds 2%, max 100

    # --------------------------
    # Raw combined score
    # --------------------------
    raw = max(0, (100 - penalties) * 0.4 + perf_weighted * 0.4 + coverage * 0.2 + link_score * 0.2)
    overall = max(0, min(100, raw))

    # --------------------------
    # Grade assignment
    # --------------------------
    grade = 'D'
    for cutoff, letter in GRADE_BANDS:
        if overall >= cutoff:
            grade = letter
            break

    # --------------------------
    # Competitor score simulation (if provided)
    # --------------------------
    competitor_comparison = {}
    if competitors:
        for name, score in competitors.items():
            competitor_comparison[name] = round(overall - score, 2)

    # --------------------------
    # Audit confidence level
    # --------------------------
    confidence = 100 - min(100, penalties + broken_links * 2)  # penalize missing elements

    # --------------------------
    # Return breakdown
    # --------------------------
    breakdown = {
        'onpage': max(0, 100 - penalties),
        'performance': round(perf_weighted, 2),
        'coverage': coverage,
        'links': round(link_score, 2),
        'confidence': round(confidence, 2),
        'competitor_comparison': competitor_comparison
    }

    return round(overall, 2), grade, breakdown
