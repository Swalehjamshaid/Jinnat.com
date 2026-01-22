# app/audit/grader.py

import logging
from typing import Dict, Any
import random

logger = logging.getLogger(__name__)


# =========================================================
# PUBLIC API – CALLED BY HTML / API / PDF
# =========================================================
def run_audit(url: str) -> Dict[str, Any]:
    """
    Runs a standardized website audit and returns a
    frontend-safe, internationally aligned audit payload.

    This output is designed to be consumed by:
    - HTML dashboards
    - PDF generators
    - REST / SaaS APIs
    """

    try:
        raw_metrics = _collect_site_metrics(url)
        category_results = _build_categories(raw_metrics)
        overall_score = _calculate_overall_score(category_results)
        grade = _assign_grade(overall_score)

        return {
            "meta": {
                "audit_version": "1.0",
                "standard": "FFTECH-WEB-AUDIT-INTL",
                "generated_by": "FFTech AI Engine",
            },
            "input": {
                "url": url,
            },
            "output": {
                "overall_score": overall_score,
                "grade": grade,
                "risk_level": _risk_from_score(overall_score),
                "summary": _executive_summary(overall_score),
            },
            "categories": category_results,
            "competitors": [],
        }

    except Exception as exc:
        logger.exception("Audit execution failed")
        return _safe_failure_response(url, str(exc))


# =========================================================
# METRIC COLLECTION (SIMULATED FOR NOW)
# =========================================================
def _collect_site_metrics(url: str) -> Dict[str, int]:
    """
    Placeholder for real scanners:
    - Google Lighthouse
    - PSI
    - OWASP ZAP
    - SEO crawlers
    """

    base_score = 40
    if "apple" in url.lower():
        base_score = 75
    elif "haier" in url.lower():
        base_score = 65

    return {
        "performance": min(100, base_score + random.randint(5, 20)),
        "seo": min(100, base_score + random.randint(5, 25)),
        "security": min(100, base_score + random.randint(5, 15)),
        "internationalization": min(100, base_score + random.randint(0, 15)),
        "content_quality": min(100, base_score + random.randint(5, 20)),
    }


# =========================================================
# CATEGORY NORMALIZATION (HTML SAFE)
# =========================================================
def _build_categories(metrics: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
    return {
        "performance": _category_block(
            "Performance",
            metrics["performance"],
            metrics
        ),
        "seo": _category_block(
            "SEO",
            metrics["seo"],
            metrics
        ),
        "security": _category_block(
            "Security",
            metrics["security"],
            metrics
        ),
        "internationalization": _category_block(
            "Internationalization",
            metrics["internationalization"],
            metrics
        ),
        "content_quality": _category_block(
            "Content Quality",
            metrics["content_quality"],
            metrics
        ),
    }


def _category_block(title: str, score: int, metrics: Dict) -> Dict[str, Any]:
    return {
        "title": title,
        "score": score,
        "status": _status_from_score(score),
        "risk_level": _risk_from_score(score),
        "business_impact": _business_impact(score),
        "metrics": metrics,
    }


# =========================================================
# SCORING & INTERPRETATION
# =========================================================
def _calculate_overall_score(categories: Dict[str, Dict]) -> float:
    """
    Internationally accepted weighted scoring model.
    """

    weights = {
        "performance": 0.30,
        "seo": 0.25,
        "security": 0.20,
        "internationalization": 0.10,
        "content_quality": 0.15,
    }

    total = 0.0
    for key, weight in weights.items():
        total += categories[key]["score"] * weight

    return round(total, 2)


def _assign_grade(score: float) -> str:
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B+"
    if score >= 60:
        return "B"
    return "C"


def _status_from_score(score: float) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Acceptable"
    if score >= 50:
        return "Needs Improvement"
    return "Critical"


def _risk_from_score(score: float) -> str:
    if score >= 85:
        return "Low"
    if score >= 70:
        return "Medium"
    return "High"


def _business_impact(score: float) -> str:
    if score >= 85:
        return "Optimized for growth and scalability"
    if score >= 70:
        return "Moderate revenue and conversion leakage"
    return "High risk of traffic, revenue, and trust loss"


def _executive_summary(score: float) -> str:
    if score >= 85:
        return "The website demonstrates strong technical health and global readiness."
    if score >= 70:
        return "The website performs adequately but shows clear optimization opportunities."
    return "The website presents critical technical and commercial risks requiring immediate action."


# =========================================================
# FAILURE SAFE (NEVER BREAK HTML)
# =========================================================
def _safe_failure_response(url: str, reason: str) -> Dict[str, Any]:
    return {
        "meta": {
            "audit_version": "1.0",
            "status": "failed",
            "reason": reason,
        },
        "input": {"url": url},
        "output": {
            "overall_score": 0,
            "grade": "N/A",
            "risk_level": "Unknown",
            "summary": "Audit could not be completed.",
        },
        "categories": {},
        "competitors": [],
    }
