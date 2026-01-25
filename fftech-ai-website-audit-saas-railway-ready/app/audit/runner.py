
# app/audit/runner.py
import asyncio
from typing import Dict, Union, Any

from .seo import analyze_onpage
from .performance import analyze_performance
from .links import analyze_links
from .grader import grade_audit
from .record import fetch_site_html
from ..settings import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

async def run_audit(url: str) -> Dict[str, Any]:
    audit_result: Dict[str, Any] = {}

    # 1️⃣ Fetch HTML
    html_docs: Union[Dict[str, str], str] = await fetch_site_html(url)
    if isinstance(html_docs, str):
        html_docs = {url: html_docs}

    # 2️⃣ SEO Analysis
    seo_metrics: Dict[str, Any] = analyze_onpage(html_docs)
    audit_result['seo'] = seo_metrics

    # 3️⃣ Performance Analysis (await properly)
    perf_metrics: Dict[str, Any] = await analyze_performance(url)
    audit_result['performance'] = perf_metrics

    # 4️⃣ Links Analysis
    link_metrics: Dict[str, Any] = analyze_links(html_docs)
    audit_result['links'] = link_metrics

    # 5️⃣ Grade (defensive)
    try:
        overall, grade, breakdown = grade_audit(seo_metrics, perf_metrics, link_metrics)
    except Exception as e:
        logger.exception("Grading failed: %s", e)
        # Fallback: minimal safe values so UI keeps working
        overall, grade, breakdown = 0, "D", {
            "onpage": 0,
            "performance": 0,
            "coverage": 0,
            "confidence": 0
        }
    audit_result['overall_score'] = overall
    audit_result['grade'] = grade
    audit_result['breakdown'] = breakdown

    # 6️⃣ Executive Summary
    audit_result['executive_summary'] = (
        f"Website {url} scored {audit_result['overall_score']} ({audit_result['grade']}). "
        "SEO, Performance, and Links metrics analyzed. Focus on improving low-scoring areas first."
    )
    audit_result['priorities'] = [
        "Fix broken links",
        "Improve page speed (LCP < 2.5s)",
        "Add missing meta descriptions",
        "Optimize images",
    ]

    # 7️⃣ Issues Overview (namespaced to avoid key collisions)
    audit_result['issues_overview'] = {
        "seo": seo_metrics,
        "performance": perf_metrics,
        "links": link_metrics
    }

    return audit_result
