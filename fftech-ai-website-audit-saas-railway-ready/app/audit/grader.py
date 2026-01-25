
# app/audit/grader.py

from typing import Dict, Tuple
from numbers import Number
import logging

logger = logging.getLogger(__name__)

def _sum_numeric_leaves(obj) -> float:
    """
    Recursively traverse dicts/lists/tuples/sets and sum numeric leaves.
    Non-numeric values (str, bool, None, objects) are ignored.
    """
    if obj is None:
        return 0.0
    if isinstance(obj, bool):
        # Prevent True/False from counting as 1/0
        return 0.0
    if isinstance(obj, Number):
        return float(obj)
    if isinstance(obj, dict):
        total = 0.0
        for v in obj.values():
            total += _sum_numeric_leaves(v)
        return total
    if isinstance(obj, (list, tuple, set)):
        total = 0.0
        for v in obj:
            total += _sum_numeric_leaves(v)
        return total
    # Ignore other types like strings
    return 0.0


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
        Robust formula: score = 100 - sum(all numeric leaves)
        (Nested dicts/lists are supported; non-numeric values are ignored.)
        """
        base = 100.0
        penalty = _sum_numeric_leaves(metrics)
        score = max(0.0, base - penalty)
        return int(round(score))

    # Optional: quick debug of incoming shapes (disabled by default)
    try:
        logger.debug("SEO metric types: %s", {k: type(v).__name__ for k, v in seo_metrics.items()})
        logger.debug("Performance metric types: %s", {k: type(v).__name__ for k, v in perf_metrics.items()})
        logger.debug("Link metric types: %s", {k: type(v).__name__ for k, v in link_metrics.items()})
    except Exception:
        pass

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


# -----------------------------
# Add compute_scores for main.py compatibility
# -----------------------------
def compute_scores(seo_metrics: Dict[str, int],
                   perf_metrics: Dict[str, int],
                   link_metrics: Dict[str, int]) -> Tuple[int, str, Dict[str, int]]:
    """
    Wrapper function to maintain import compatibility with main.py.
    """
    return grade_audit(seo_metrics, perf_metrics, link_metrics)
``
