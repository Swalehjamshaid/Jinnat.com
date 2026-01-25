# app/audit/runner.py
import time
from typing import Dict, Union, Any
from .seo import analyze_onpage
from .performance import analyze_performance      # must be synchronous now
from .links import analyze_links
from .grader import grade_audit
from .record import fetch_site_html               # must be synchronous now
from ..settings import get_settings

settings = get_settings()


def sanitize_resource(resource: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only lightweight, essential fields from resource objects."""
    keys_to_keep = ["url", "statusCode", "resourceType", "transferSize", "resourceSize", "finished"]
    return {k: resource.get(k) for k in keys_to_keep if k in resource}


def sanitize_page_elements(elements: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only position/size info — discard heavy or redundant data."""
    sanitized = {}
    for key, value in elements.items():
        if isinstance(value, dict):
            sanitized[key] = {
                pos_key: value.get(pos_key)
                for pos_key in ["top", "bottom", "left", "right", "width", "height"]
                if pos_key in value
            }
        else:
            sanitized[key] = value  # fallback
    return sanitized


def run_audit(url: str) -> Dict[str, Any]:
    """
    Runs a full website audit (synchronous version - no asyncio/await).
    """
    audit_result: Dict[str, Any] = {}

    # 1. Fetch HTML pages (synchronous call - NO await)
    html_docs: Union[Dict[str, str], str] = fetch_site_html(url)

    # Normalize to dict
    if isinstance(html_docs, str):
        html_docs = {url: html_docs}
    elif not isinstance(html_docs, dict):
        html_docs = {}  # safety fallback

    audit_result["crawled_pages"] = list(html_docs.keys())

    # 2. SEO Analysis
    seo_metrics = analyze_onpage(html_docs)
    audit_result["seo"] = seo_metrics

    # 3. Performance Analysis (synchronous call - NO await)
    perf_metrics = analyze_performance(url)

    # Sanitize performance data
    if isinstance(perf_metrics, dict):
        if "resources" in perf_metrics and isinstance(perf_metrics["resources"], (list, tuple)):
            perf_metrics["resources"] = [
                sanitize_resource(r) for r in perf_metrics["resources"]
                if isinstance(r, dict)
            ]

        if "page_elements" in perf_metrics and isinstance(perf_metrics["page_elements"], dict):
            perf_metrics["page_elements"] = sanitize_page_elements(perf_metrics["page_elements"])

    audit_result["performance"] = perf_metrics or {}

    # 4. Links analysis
    link_metrics = analyze_links(html_docs)
    audit_result["links"] = link_metrics

    # 5. Grade & breakdown
    overall_score, grade, breakdown = grade_audit(
        seo_metrics=seo_metrics,
        performance_metrics=perf_metrics or {},
        links_metrics=link_metrics
    )

    audit_result["overall_score"] = overall_score
    audit_result["grade"] = grade
    audit_result["breakdown"] = breakdown

    # 6. Executive summary
    audit_result["executive_summary"] = (
        f"Website {url} received an overall score of {overall_score} ({grade}). "
        f"Analyzed {len(html_docs)} page(s). "
        "Prioritize fixing low-performing categories."
    )

    # 7. Priorities (make dynamic based on real data)
    priorities = ["Optimize images and reduce page size"]
    
    if isinstance(perf_metrics, dict) and perf_metrics.get("lcp_ms", 9999) > 2500:
        priorities.append("Reduce Largest Contentful Paint (LCP < 2.5s recommended)")
    if link_metrics.get("broken_count", 0) > 0:
        priorities.append("Fix broken internal/external links")
    if seo_metrics.get("meta_description_missing", 0) > 0:
        priorities.append("Add or improve meta descriptions")

    audit_result["priorities"] = priorities[:5]

    # 8. Flat issues overview
    audit_result["issues_overview"] = {
        **(seo_metrics or {}),
        **(perf_metrics or {}),
        **(link_metrics or {}),
    }

    # 9. Completion markers
    audit_result["finished"] = True
    audit_result["audit_completed_at"] = int(time.time())

    return audit_result
