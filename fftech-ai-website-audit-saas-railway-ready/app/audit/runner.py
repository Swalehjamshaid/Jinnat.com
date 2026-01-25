# app/audit/runner.py
from typing import Dict, Union, Any
from .seo import analyze_onpage
from .performance import analyze_performance     # ← must be synchronous now
from .links import analyze_links
from .grader import grade_audit
from .record import fetch_site_html              # ← must be synchronous now
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
            sanitized[key] = value  # fallback: keep as-is if not dict
    return sanitized


def run_audit(url: str) -> Dict[str, Any]:
    """
    Runs a full website audit (synchronous / blocking version).

    Steps:
      1. Fetch HTML (single page or multiple)
      2. On-page SEO analysis
      3. Performance analysis
      4. Links analysis
      5. Compute overall grade & score
      6. Generate summary & priorities

    Returns: unified audit report dictionary
    """
    audit_result: Dict[str, Any] = {}

    # 1. Fetch HTML pages (now synchronous)
    html_docs: Union[Dict[str, str], str] = fetch_site_html(url)

    # Normalize to dict even if single page was returned
    if isinstance(html_docs, str):
        html_docs = {url: html_docs}
    elif not isinstance(html_docs, dict):
        html_docs = {}  # safety fallback

    audit_result["crawled_pages"] = list(html_docs.keys())  # useful for reporting

    # 2. SEO Analysis (on-page metrics from HTML)
    seo_metrics = analyze_onpage(html_docs)
    audit_result["seo"] = seo_metrics

    # 3. Performance Analysis (now synchronous)
    perf_metrics = analyze_performance(url)

    # Sanitize performance data to keep response size reasonable
    if isinstance(perf_metrics, dict):
        if "resources" in perf_metrics and isinstance(perf_metrics["resources"], list):
            perf_metrics["resources"] = [
                sanitize_resource(r) for r in perf_metrics["resources"]
                if isinstance(r, dict)
            ]

        if "page_elements" in perf_metrics and isinstance(perf_metrics["page_elements"], dict):
            perf_metrics["page_elements"] = sanitize_page_elements(perf_metrics["page_elements"])

    audit_result["performance"] = perf_metrics

    # 4. Links Coverage / Broken links analysis
    link_metrics = analyze_links(html_docs)
    audit_result["links"] = link_metrics

    # 5. Grade & breakdown
    overall_score, grade, breakdown = grade_audit(
        seo_metrics=seo_metrics,
        performance_metrics=perf_metrics,
        links_metrics=link_metrics
    )

    audit_result["overall_score"] = overall_score
    audit_result["grade"] = grade
    audit_result["breakdown"] = breakdown

    # 6. Executive summary
    audit_result["executive_summary"] = (
        f"Website {url} received an overall score of {overall_score} ({grade}). "
        f"Analyzed {len(html_docs)} page(s). "
        "Prioritize fixing low-performing categories (especially if Performance or Links < 70)."
    )

    # 7. Suggested priorities (dynamic based on scores — can be improved later)
    priorities = ["Optimize images and reduce page size"]
    
    if perf_metrics.get("lcp_ms", 9999) > 2500:
        priorities.append("Reduce Largest Contentful Paint (LCP < 2.5s)")
    if link_metrics.get("broken_count", 0) > 0:
        priorities.append("Fix broken internal/external links")
    if seo_metrics.get("meta_description_missing", 0) > 0:
        priorities.append("Add or improve meta descriptions")
    if seo_metrics.get("title_issues", 0) > 0:
        priorities.append("Fix title tag length & uniqueness")

    audit_result["priorities"] = priorities[:5]  # limit to top 5

    # 8. Flat issues overview (for quick display / charts)
    audit_result["issues_overview"] = {
        **seo_metrics,
        **perf_metrics,
        **link_metrics,
    }

    # 9. Completion marker (useful for UI polling / SSE if you keep that)
    audit_result["finished"] = True
    audit_result["audit_completed_at"] = int(time.time())  # unix timestamp

    return audit_result
