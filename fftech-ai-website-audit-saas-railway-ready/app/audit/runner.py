# app/audit/runner.py
import asyncio
from typing import Dict, Union

from .seo import analyze_onpage
from .performance import analyze_performance
from .links import analyze_links
from .grader import grade_audit
from .record import fetch_site_html
from ..settings import get_settings

settings = get_settings()


def sanitize_resource(resource: dict) -> dict:
    """Keep only essential fields from resource to avoid duplicates and huge JSON."""
    keys_to_keep = ["url", "statusCode", "resourceType", "transferSize", "resourceSize", "finished"]
    return {k: resource.get(k) for k in keys_to_keep if k in resource}


def sanitize_page_elements(elements: dict) -> dict:
    """Flatten page element info, remove duplicates, keep positions only."""
    sanitized = {}
    for k, v in elements.items():
        sanitized[k] = {key: v[key] for key in ["top", "bottom", "left", "right", "width", "height"] if key in v}
    return sanitized


async def run_audit(url: str) -> Dict:
    """
    Runs a full website audit asynchronously.
    Steps:
      1. Crawl site & fetch HTML
      2. SEO analysis
      3. Performance analysis
      4. Links coverage analysis
      5. Grade computation
    Returns a unified audit report dictionary.
    """
    audit_result = {}

    # 1️⃣ Fetch HTML pages
    html_docs: Union[Dict[str, str], str] = await fetch_site_html(url)

    # Ensure html_docs is always a dictionary
    if isinstance(html_docs, str):
        html_docs = {url: html_docs}

    # 2️⃣ SEO Analysis
    seo_metrics = analyze_onpage(html_docs)
    audit_result["seo"] = seo_metrics

    # 3️⃣ Performance Analysis
    perf_metrics = await analyze_performance(url)

    # Sanitize performance result to remove unnecessary duplicates
    if "resources" in perf_metrics:
        perf_metrics["resources"] = [sanitize_resource(r) for r in perf_metrics["resources"]]
    if "page_elements" in perf_metrics:
        perf_metrics["page_elements"] = sanitize_page_elements(perf_metrics["page_elements"])

    audit_result["performance"] = perf_metrics

    # 4️⃣ Links Coverage Analysis
    link_metrics = analyze_links(html_docs)
    audit_result["links"] = link_metrics

    # 5️⃣ Grade & Overall Score
    audit_result["overall_score"], audit_result["grade"], audit_result["breakdown"] = grade_audit(
        seo_metrics, perf_metrics, link_metrics
    )

    # 6️⃣ Executive Summary & Priorities
    audit_result["executive_summary"] = (
        f"Website {url} scored {audit_result['overall_score']} ({audit_result['grade']}). "
        "SEO, Performance, and Links metrics analyzed. Focus on improving low-scoring areas first."
    )
    audit_result["priorities"] = [
        "Fix broken links",
        "Improve page speed (LCP < 2.5s)",
        "Add missing meta descriptions",
        "Optimize images",
    ]

    # 7️⃣ Issues Overview
    audit_result["issues_overview"] = {**seo_metrics, **perf_metrics, **link_metrics}

    # 8️⃣ Finished flag for SSE
    audit_result["finished"] = True

    return audit_result
