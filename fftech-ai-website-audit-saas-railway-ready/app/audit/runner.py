from .record import fetch_site_html
from .seo import analyze_onpage
from .performance import analyze_performance
from .links import analyze_links
from .grader import grade_audit

def run_audit(url: str):
    html_docs = fetch_site_html(url)
    seo = analyze_onpage(html_docs)
    perf = analyze_performance(url)
    links = analyze_links(html_docs)
    overall_score, grade, breakdown = grade_audit(seo, perf, links)
    return {
        "seo": seo,
        "performance": perf,
        "links": links,
        "overall_score": overall_score,
        "grade": grade,
        "breakdown": breakdown
    }
