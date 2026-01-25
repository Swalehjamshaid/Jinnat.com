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

async def run_audit(url: str) -> Dict:
    audit_result = {}

    # Fetch HTML pages
    html_docs: Union[Dict[str, str], str] = await fetch_site_html(url)
    if isinstance(html_docs, str):
        html_docs = {url: html_docs}

    # SEO analysis
    seo_metrics = analyze_onpage(html_docs)
    audit_result['seo'] = seo_metrics

    # Performance analysis
    perf_metrics = await analyze_performance(url)
    audit_result['performance'] = perf_metrics

    # Links analysis
    link_metrics = analyze_links(html_docs)
    audit_result['links'] = link_metrics

    # Compute grade
    audit_result['overall_score'], audit_result['grade'], audit_result['breakdown'] = grade_audit(
        seo_metrics, perf_metrics, link_metrics
    )

    # Executive summary & priorities
    audit_result['executive_summary'] = (
        f"Website {url} scored {audit_result['overall_score']} ({audit_result['grade']}). "
        "SEO, Performance, and Links metrics analyzed."
    )
    audit_result['priorities'] = [
        "Fix broken links",
        "Improve page speed (LCP < 2.5s)",
        "Add missing meta descriptions",
        "Optimize images",
    ]

    # Issues overview
    audit_result['issues_overview'] = {**seo_metrics, **perf_metrics, **link_metrics}

    return audit_result
