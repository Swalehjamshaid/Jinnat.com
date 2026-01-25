# app/audit/runner.py
from typing import Dict, Union
from .seo import analyze_onpage
from .performance import analyze_performance
from .links import analyze_links
from .grader import grade_audit
from .record import fetch_site_html

def run_audit(url: str, max_pages: int = 20) -> Dict:
    """
    Runs full Python-native audit:
    - HTML crawl
    - SEO analysis
    - Performance analysis
    - Links coverage
    - Grade computation
    """
    audit_result = {}

    # 1️⃣ Fetch HTML
    html_docs: Union[Dict[str, str], str] = fetch_site_html(url, max_pages=max_pages)
    if isinstance(html_docs, str):
        html_docs = {url: html_docs}

    # 2️⃣ SEO
    seo_metrics = analyze_onpage(html_docs)
    audit_result["seo"] = seo_metrics

    # 3️⃣ Performance
    perf_metrics = analyze_performance(url)
    audit_result["performance"] = perf_metrics

    # 4️⃣ Links
    link_metrics = analyze_links(html_docs)
    audit_result["links"] = link_metrics

    # 5️⃣ Grade
    audit_result["overall_score"], audit_result["grade"], audit_result["breakdown"] = grade_audit(
        seo_metrics, perf_metrics, link_metrics
    )

    # 6️⃣ Executive summary & priorities
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

    # 7️⃣ Issues overview
    audit_result["issues_overview"] = {**seo_metrics, **perf_metrics, **link_metrics}

    # 8️⃣ Finished flag
    audit_result["finished"] = True

    return audit_result
