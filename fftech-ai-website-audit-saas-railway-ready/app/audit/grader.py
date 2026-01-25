# app/app/audit/grader.py
import logging
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)


def sum_numeric_penalties(obj: Any, max_depth: int = 20) -> float:
    """
    Recursively sum all numeric values (int/float) found in the object.

    - Ignores: strings, booleans, None, non-numeric types
    - Handles: dict, list, tuple, set (and nested combinations)
    - Skips very deep nesting to prevent stack overflow on malformed data
    """
    if max_depth <= 0:
        logger.warning("Max recursion depth reached in sum_numeric_penalties")
        return 0.0

    if obj is None or isinstance(obj, bool):
        return 0.0

    if isinstance(obj, (int, float)):
        return float(obj)

    total = 0.0

    if isinstance(obj, dict):
        for value in obj.values():
            total += sum_numeric_penalties(value, max_depth - 1)

    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            total += sum_numeric_penalties(item, max_depth - 1)

    # Everything else (str, bytes, custom objects, etc.) → ignored → 0

    return total


def calculate_category_score(metrics: Dict[str, Any]) -> int:
    """
    Convert raw metrics dict → score 0–100.

    Logic: start at 100, subtract sum of all numeric values found anywhere
    (penalties are assumed to be positive numbers).
    Clamp result to [0, 100].
    """
    base = 100.0
    penalty = sum_numeric_penalties(metrics)
    score = max(0.0, base - penalty)
    return int(round(score))


def grade_audit(
    seo_metrics: Dict[str, Any],
    performance_metrics: Dict[str, Any],
    links_metrics: Dict[str, Any],
) -> Tuple[int, str, Dict[str, int]]:
    """
    Compute overall audit score, letter grade, and category breakdown.

    Weights (configurable if needed later):
      SEO          → 40%
      Performance  → 40%
      Links        → 20%

    Returns:
        (overall_score: int, grade: str, breakdown: Dict[str, int])
    """
    # ── Calculate individual category scores ──
    seo_score         = calculate_category_score(seo_metrics)
    performance_score = calculate_category_score(performance_metrics)
    links_score       = calculate_category_score(links_metrics)

    # ── Weighted overall score ──
    overall = round(
        seo_score         * 0.40 +
        performance_score * 0.40 +
        links_score       * 0.20
    )
    overall = max(0, min(100, overall))  # just in case of rounding weirdness

    # ── Letter grade ──
    if overall >= 90:
        grade = "A"
    elif overall >= 75:
        grade = "B"
    elif overall >= 60:
        grade = "C"
    elif overall >= 40:
        grade = "D"
    else:
        grade = "F"   # more conventional than stopping at D

    # ── Breakdown for charts / UI (keys can be adjusted to match frontend) ──
    breakdown = {
        "seo":          seo_score,
        "performance":  performance_score,
        "links":        links_score,
        "overall":      overall,         # sometimes shown as "confidence" or "total"
    }

    # Optional: log for debugging (remove in production if too verbose)
    logger.debug(
        "Audit grading → SEO:%d | Perf:%d | Links:%d | Total:%d (%s)",
        seo_score, performance_score, links_score, overall, grade
    )

    return overall, grade, breakdown


# Backward-compatibility alias (if old code still calls this name)
compute_scores = grade_audit
