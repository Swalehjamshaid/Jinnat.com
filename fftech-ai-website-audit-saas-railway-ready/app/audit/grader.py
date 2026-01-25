
# app/app/audit/grader.py

from typing import Dict, Tuple, Any
from numbers import Number
import logging

logger = logging.getLogger(__name__)

def _sum_numeric_leaves(obj: Any) -> float:
    """
    Recursively traverse dicts/lists/tuples/sets and sum numeric leaves.
    Ignores None, strings, booleans, and other non-numeric types.
    """
    if obj is None:
        return 0.0
    if isinstance(obj, bool):
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
    return 0.0


def grade_audit(
    seo_metrics: Dict[str, Any],
    perf_metrics: Dict[str, Any],
    link_metrics: Dict[str, Any]
) -> Tuple[int, str, Dict[str, int]]:
    """
    Calculates overall audit score, assigns grade, and breakdown for charts.

    Weights:
      - SEO: 40%
      - Performance: 40%
      - Links: 20%

    Each group score starts at 100 and subtracts the sum of numeric leaves
    found anywhere in that group's metrics (nested dicts/lists supported).
    """

    def score_from_metrics(metrics: Dict[str, Any]) -> int:
        base = 100.0
        penalty = _sum_numeric_leaves(metrics)
        score = max(0.0, base - penalty)
        return int(round(score))

    # Optional debug to inspect shapes without crashing
    try:
        logger.debug("SEO metric field types: %s", {k: type(v).__name__ for k, v in seo_metrics.items()})
        logger.debug("Performance metric field types: %s", {k: type(v).__name__ for k, v in perf_metrics.items()})
        logger.debug("Links metric field types: %s", {k: type(v).__name__ for k, v in link_metrics.items()})
    except Exception:
        pass

    # 1) Individual scores
    seo_score = score_from_metrics(seo_metrics)
    perf_score = score_from_metrics(perf_metrics)
    links_score = score_from_metrics(link_metrics)

    # 2) Weighted overall score
    overall_score = round(
        (seo_score * 0.4) +
        (perf_score * 0.4) +
        (links_score * 0.2)
    )

    # 3) Grade mapping
    if overall_score >= 90:
        grade = "A"
    elif overall_score >= 75:
        grade = "B"
    elif overall_score >= 60:
        grade = "C"
    else:
        grade = "D"

    # 4) Breakdown for charts
    breakdown = {
        "onpage": seo_score,
        "performance": perf_score,
        "coverage": links_score,
        "confidence": overall_score
    }

    return overall_score, grade, breakdown


def compute_scores(seo_metrics: Dict[str, Any],
                   perf_metrics: Dict[str, Any],
                   link_metrics: Dict[str, Any]) -> Tuple[int, str, Dict[str, int]]:
    """
    Backward-compatible wrapper.
    """
    return grade_audit(seo_metrics, perf_metrics, link_metrics)
