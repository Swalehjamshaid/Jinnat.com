# app/audit/grader.py
from typing import Tuple, Dict

def grade_audit(seo_metrics: Dict[str, int], perf_metrics: Dict[str, int], link_metrics: Dict[str, int]) -> Tuple[int, str, Dict[str, int]]:
    """
    Returns:
    - overall_score (0-100)
    - grade (A-F)
    - breakdown
    """
    seo_score = 100 - (
        seo_metrics["missing_title"] +
        seo_metrics["missing_meta_description"] +
        seo_metrics["missing_h1"] +
        seo_metrics["images_missing_alt"] +
        seo_metrics["broken_links"]
    ) * 5

    perf_score = 100 - (perf_metrics["lcp_ms"] // 1000) * 5
    links_score = 100 - (link_metrics["external_links_count"] // 10)

    seo_score = max(0, min(100, seo_score))
    perf_score = max(0, min(100, perf_score))
    links_score = max(0, min(100, links_score))

    overall_score = int((seo_score + perf_score + links_score) / 3)

    if overall_score >= 90:
        grade = "A"
    elif overall_score >= 75:
        grade = "B"
    elif overall_score >= 60:
        grade = "C"
    elif overall_score >= 45:
        grade = "D"
    else:
        grade = "F"

    return overall_score, grade, {"seo": seo_score, "performance": perf_score, "links": links_score}
