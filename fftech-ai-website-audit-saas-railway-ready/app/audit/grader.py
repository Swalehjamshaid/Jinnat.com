# app/audit/grader.py

from typing import Dict, Tuple

def grade_audit(
    seo_metrics: Dict[str, int],
    perf_metrics: Dict[str, int],
    link_metrics: Dict[str, int]
) -> Tuple[int, str, Dict[str, int]]:
    """
    Calculates overall audit score, assigns grade, and breakdown for charts.

    Weights (example):
      - SEO: 40%
      - Performance: 40%
      - Links: 20%
    """

    # --- 1. Calculate individual scores ---
    def score_from_metrics(metrics: Dict[str, int]) -> int:
        """
        Each metric reduces score from 100 based on severity.
        Simple formula: score = 100 - sum(metric penalties)
        """
        base = 100
        penalty = sum(metrics.values())
        score = max(0, base - penalty)
        return score

    seo_score = score_from_metrics(seo_metrics)
    perf_score = score_from_metrics(perf_metrics)
    links_score = score_from_metrics(link_metrics)

    # --- 2. Weighted overall score ---
    overall_score = round(
        (seo_score * 0.4) +
        (perf_score * 0.4) +
        (links_score * 0.2)
    )

    # --- 3. Assign grade ---
    if overall_score >= 90:
        grade = "A"
    elif overall_score >= 75:
        grade = "B"
    elif overall_score >= 60:
        grade = "C"
    else:
        grade = "D"

    # --- 4. Prepare breakdown for chart ---
    breakdown = {
        "onpage": seo_score,
        "performance": perf_score,
        "coverage": links_score,
        "confidence": overall_score  # For AI confidence in UI charts
    }

    return overall_score, grade, breakdown
