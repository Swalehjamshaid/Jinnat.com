# app/audit/grader.py

import math
from typing import Dict, List

def normalize_score(value, max_val=100, min_val=0):
    """Normalize metric to 0-100 scale safely."""
    if value is None:
        return 0
    value = max(min_val, min(value, max_val))
    return (value - min_val) / (max_val - min_val) * 100

def score_core_web_vitals(metrics: Dict) -> float:
    """Technical scoring based on Core Web Vitals."""
    lcp = metrics.get('lcp')  # Largest Contentful Paint in seconds
    cls = metrics.get('cls')  # Cumulative Layout Shift
    inp = metrics.get('inp')  # Interaction to Next Paint in ms

    lcp_score = max(0, 100 - (lcp or 5) / 2.5 * 100)  # Faster LCP -> higher score
    cls_score = max(0, 100 - (cls or 0.5) * 200)      # CLS <0.1 -> 100
    inp_score = max(0, 100 - (inp or 2000) / 2000 * 100)  # INP <200ms -> 100

    return (lcp_score * 0.4 + cls_score * 0.3 + inp_score * 0.3)

def score_seo(metrics: Dict) -> float:
    """SEO scoring based on meta, headings, content, links."""
    title = 1 if metrics.get('title_present') else 0
    meta = 1 if metrics.get('meta_description') else 0
    headings = metrics.get('headings_score', 0)
    links = metrics.get('internal_links_score', 0)
    content = metrics.get('content_score', 0)

    raw = (title * 10 + meta * 10 + headings * 25 + links * 25 + content * 30)
    return normalize_score(raw, 100)

def score_security(metrics: Dict) -> float:
    """Security & best practices scoring."""
    https = 100 if metrics.get('https', False) else 0
    headers = metrics.get('security_headers_score', 0)
    robots = 10 if metrics.get('robots') else 0
    sitemap = 10 if metrics.get('sitemap') else 0
    vulns = metrics.get('vulnerabilities', 0)
    vulns_score = max(0, 100 - vulns * 20)  # Each vulnerability reduces score

    return (https * 0.4 + headers * 0.3 + (robots + sitemap) * 0.3 + vulns_score * 0.0)

def score_ux(metrics: Dict) -> float:
    """UX & accessibility scoring."""
    mobile = 100 if metrics.get('mobile_friendly') else 50
    nav = metrics.get('navigation_score', 0)
    contrast = metrics.get('color_contrast_score', 0)
    aria = metrics.get('aria_score', 0)

    return normalize_score(mobile * 0.25 + nav * 0.25 + contrast * 0.25 + aria * 0.25, 100)

def score_international(metrics: Dict) -> float:
    """Internationalization & export readiness."""
    hreflang = 25 if metrics.get('hreflang') else 0
    multi_lang = 25 if metrics.get('multi_language') else 0
    export_pages = metrics.get('export_pages_score', 0)
    compliance = metrics.get('intl_compliance', 0)

    return normalize_score(hreflang + multi_lang + export_pages + compliance, 100)

def per_page_opportunity(metrics: List[Dict]) -> float:
    """Deduct points for missing meta, thin content, broken links."""
    total_pages = len(metrics)
    if total_pages == 0:
        return 0
    deductions = 0
    for page in metrics:
        if not page.get('title_present'):
            deductions += 3
        if not page.get('meta_description'):
            deductions += 3
        if page.get('content_score', 0) < 50:
            deductions += 5
        if page.get('broken_links', 0) > 0:
            deductions += min(page.get('broken_links',0)*2, 10)
    avg_deduction = min(deductions / total_pages, 20)  # Max deduction 20%
    return avg_deduction

def calculate_overall_score(metrics: Dict, page_metrics: List[Dict]=None) -> float:
    """Weighted overall score combining all categories + per-page deductions."""
    tech = score_core_web_vitals(metrics)
    seo = score_seo(metrics)
    sec = score_security(metrics)
    ux = score_ux(metrics)
    intl = score_international(metrics)

    weighted = (
        tech * 0.4 +
        seo * 0.25 +
        sec * 0.15 +
        ux * 0.1 +
        intl * 0.1
    )

    if page_metrics:
        deduction = per_page_opportunity(page_metrics)
        weighted = max(0, weighted - deduction)

    return round(weighted, 2)

def assign_grade(score: float) -> str:
    if score >= 85:
        return "A+"
    elif score >= 75:
        return "A"
    elif score >= 65:
        return "B+"
    elif score >= 50:
        return "B"
    else:
        return "C"

def run_audit(metrics: Dict, page_metrics: List[Dict]=None) -> Dict:
    """
    Input: metrics dictionary with all scoring metrics
           page_metrics list for per-page analysis
    Output: audit report dictionary
    """
    overall = calculate_overall_score(metrics, page_metrics)
    grade = assign_grade(overall)

    categories = {
        "Technical": {"score": score_core_web_vitals(metrics), "metrics": metrics},
        "SEO": {"score": score_seo(metrics), "metrics": metrics},
        "Security": {"score": score_security(metrics), "metrics": metrics},
        "UX & Accessibility": {"score": score_ux(metrics), "metrics": metrics},
        "Internationalization": {"score": score_international(metrics), "metrics": metrics}
    }

    return {
        "overall_score": overall,
        "grade": grade,
        "categories": categories
    }
