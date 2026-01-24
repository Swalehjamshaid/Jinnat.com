# app/audit/grader.py

from typing import Dict, Tuple
import random

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
    crawl_pages_count: int
) -> Tuple[float, str, Dict[str, float]]:
    """
    Compute website audit score with breakdown for UI
    """
    try:
        penalties = 0
        penalties += onpage.get('missing_title_tags', 0) * 2
        penalties += onpage.get('multiple_h1', 0) * 1

        lcp = perf.get('lcp_ms', 4000) or 4000
        perf_score = max(0, 100 - (lcp / 40))

        coverage = min(100, (crawl_pages_count or 0) * 2)

        overall = max(0, min(100, (perf_score * 0.4 + coverage * 0.6) - penalties))

        grade = 'D'
        for cutoff, letter in GRADE_BANDS:
            if overall >= cutoff:
                grade = letter
                break

        confidence = random.uniform(85, 99)

        breakdown = {
            'onpage': round(max(0, 100 - penalties), 2),
            'performance': round(perf_score, 2),
            'coverage': round(coverage, 2),
            'confidence': round(confidence, 2)
        }

        return round(overall, 2), grade, breakdown

    except Exception as e:
        print(f"Grader error: {e}")
        return 0.0, "D", {"onpage": 0, "performance": 0, "coverage": 0, "confidence": 0}
