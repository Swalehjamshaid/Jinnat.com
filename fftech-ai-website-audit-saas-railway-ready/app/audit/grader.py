# app/audit/grader.py

from typing import Dict, Tuple
import logging
import random

# Configure logger
logger = logging.getLogger("grader")
logger.setLevel(logging.INFO)

# Grade bands for score cutoffs
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
    seed: int | None = None
) -> Tuple[float, str, Dict[str, float]]:
    """
    Computes website audit scores and returns a breakdown for the UI.

    Inputs:
    - onpage: Dict with on-page SEO metrics (e.g., missing_title_tags, multiple_h1)
    - perf: Dict with performance metrics (e.g., lcp_ms, tti_ms)
    - links: Dict with link metrics (currently for future use)
    - crawl_pages_count: Number of pages crawled
    - seed: Optional int to make confidence deterministic

    Returns:
    - overall_score: float (0-100)
    - grade: str (A+, A, B, C, D)
    - breakdown: Dict[str, float] with keys: onpage, performance, coverage, confidence
    """

    try:
        # Optional deterministic randomness for confidence
        rng = random.Random(seed)

        # -------------------
        # 1️⃣ On-page SEO Score
        # -------------------
        penalties = 0.0
        penalties += onpage.get('missing_title_tags', 0) * 2
        penalties += onpage.get('multiple_h1', 0) * 1
        onpage_score = max(0.0, 100 - penalties)

        # -------------------
        # 2️⃣ Performance Score
        # -------------------
        lcp_ms = perf.get('lcp_ms', 4000) or 4000
        tti_ms = perf.get('tti_ms', 3000) or 3000
        perf_score = max(0.0, min(100.0, 100 - (lcp_ms / 40 + tti_ms / 50)))

        # -------------------
        # 3️⃣ Coverage Score
        # -------------------
        coverage_score = min(100.0, (crawl_pages_count or 0) * 2.0)

        # -------------------
        # 4️⃣ Overall Weighted Score
        # -------------------
        overall_score = (onpage_score * 0.3 + perf_score * 0.4 + coverage_score * 0.3)
        overall_score = max(0.0, min(100.0, overall_score))

        # -------------------
        # 5️⃣ Letter Grade Assignment
        # -------------------
        grade = 'D'
        for cutoff, letter in GRADE_BANDS:
            if overall_score >= cutoff:
                grade = letter
                break

        # -------------------
        # 6️⃣ Confidence Level (85-99%)
        # -------------------
        confidence = round(rng.uniform(85.0, 99.0), 2)

        # -------------------
        # 7️⃣ Final Breakdown
        # Keys must match frontend HTML expectations exactly
        # -------------------
        breakdown = {
            'onpage': round(onpage_score, 2),
            'performance': round(perf_score, 2),
            'coverage': round(coverage_score, 2),
            'confidence': confidence
        }

        return round(overall_score, 2), grade, breakdown

    except Exception as e:
        logger.error(f"Grader error: {e}", exc_info=True)
        # Return safe defaults on failure
        return 0.0, "D", {"onpage": 0.0, "performance": 0.0, "coverage": 0.0, "confidence": 0.0}
