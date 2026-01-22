import time
from app.audit.crawler import perform_crawl
from app.audit.seo import run_seo_audit
from app.audit.performance import get_performance_metrics
from app.audit.links import check_links
from app.audit.competitor_report import run_competitor_audit

def run_audit(url: str):
    """
    Main orchestrator for the 200-metric international audit.
    Integrates all modules for a smooth scanning experience.
    """
    # 1. Start Initial Crawl
    crawl_obj = perform_crawl(str(url))
    
    # 2. Run Modular Audit Providers
    seo_res = run_seo_audit(crawl_obj)
    perf_res = get_performance_metrics(url)
    link_res = check_links(crawl_obj)
    comp_res = run_competitor_audit(url)
    
    # 3. Aggregate Into Standard Categories A-I
    categories = {
        "A. Executive Summary": {
            "score": seo_res['score'], 
            "metrics": {"1_Global_Health": seo_res['score'], "6_Priority_Fix": "SEO Tags"}, 
            "color": "#4F46E5"
        },
        "D. On-Page SEO": seo_res,
        "E. Performance": perf_res,
        "G. Competitor": comp_res,
        "H. Links Intelligence": {
            "score": max(0, 100 - (link_res['total_broken_links'] * 10)),
            "metrics": {
                "168_Total_Broken": link_res['total_broken_links'],
                "169_Internal_Broken": link_res['internal_broken_links']
            },
            "color": "#EC4899"
        }
    }
    
    ov_score = sum(c['score'] for c in categories.values()) / len(categories)
    
    return {
        "url": url,
        "overall_score": round(ov_score, 2),
        "grade": "A+" if ov_score >= 90 else "A" if ov_score >= 80 else "B",
        "timestamp": int(time.time()),
        "categories": categories
    }
