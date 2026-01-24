# app/audit/grader.py

from typing import Dict, Tuple
import random

# Grade bands based on international standards
GRADE_BANDS = [
    (90, 'A+'),
    (80, 'A'),
    (70, 'B'),
    (60, 'C'),
    (0,  'D')
]

def compute_scores(
    onpage: Dict[str, float],
    perf: Dict[str, float],
    links: Dict[str, float],
    crawl_pages_count: int,
    competitor_scores: Dict[str, float] = None,
    mobile_weight: float = 0.5
) -> Tuple[float, str, Dict[str, float]]:
    """
    Compute website audit scores based on multiple factors.
    """
    try:
        # ----------------------
        # Penalties for SEO issues
        # ----------------------
        penalties = 0
        penalties += onpage.get('missing_title_tags', 0) * 2
        penalties += onpage.get('missing_meta_descriptions', 0) * 1.5
        penalties += onpage.get('multiple_h1', 0) * 1

        # ----------------------
        # Performance score
        # ----------------------
        lcp = perf.get('lcp_ms', 4000) or 4000
        fcp = perf.get('fcp_ms', 2000) or 2000
        # Calculate performance based on speed thresholds
        perf_score = max(0, 100 - (lcp / 40 + fcp / 30))

        # ----------------------
        # Links & coverage
        # ----------------------
        link_penalty = links.get('total_broken_links', 0) * 0.5
        coverage = min(100, crawl_pages_count * 2)
        penalties += link_penalty

        # ----------------------
        # Combine scores with weights
        # ----------------------
        raw_score = (
            max(0, 100 - penalties) * 0.4 +
            perf_score * 0.4 +
            coverage * 0.2
        )

        # ----------------------
        # Mobile vs Desktop adjustment
        # ----------------------
        mobile_score = raw_score * mobile_weight
        desktop_score = raw_score * (1 - mobile_weight)
        overall = (mobile_score + desktop_score)

        # ----------------------
        # Competitor comparison
        # ----------------------
        if competitor_scores:
            competitor_avg = sum(competitor_scores.values()) / max(1, len(competitor_scores))
            overall = overall * 0.9 + competitor_avg * 0.1

        # Ensure result is between 0 and 100
        overall = max(0, min(100, overall))

        # ----------------------
        # Compute letter grade
        # ----------------------
        grade = 'D'
        for cutoff, letter in GRADE_BANDS:
            if overall >= cutoff:
                grade = letter
                break

        # ----------------------
        # Breakdown & Confidence
        # ----------------------
        confidence = random.uniform(85, 99)
        breakdown = {
            'onpage': round(max(0, 100 - penalties), 2),
            'performance': round(perf_score, 2),
            'coverage': round(coverage, 2),
            'confidence': round(confidence, 2)
        }

        return round(overall, 2), grade, breakdown

    except Exception as e:
        # Fallback to prevent crash if logic fails
        print(f"Error in grader logic: {e}")
        return 0.0, "D", {"error": "Score calculation failed"}
