import time
import os
from app.audit.crawler import perform_crawl
from app.audit.seo import run_seo_audit
from app.audit.performance import get_performance_metrics
from app.audit.psi import fetch_psi
from app.audit.links import check_links


def run_audit(url: str):
    """
    Orchestrates the 200-metric audit suite with real data.
    """
    # Use env var or default 50 pages for real audit
    max_pages = int(os.getenv("MAX_CRAWL_PAGES", "50"))
    crawl_obj = perform_crawl(url, max_pages=max_pages)

    seo_res = run_seo_audit(crawl_obj)
    perf_res = get_performance_metrics(url)

    broken_links = getattr(crawl_obj, 'broken_internal', [])
    broken_count = len(broken_links)

    seo_score = seo_res.get('score', 70.0)
    perf_score = perf_res.get('score', 65.0)

    categories = {
        "A. Executive Summary": {
            "score": round((seo_score + perf_score) / 2, 1),
            "metrics": {
                "Overall Health": f"{round((seo_score + perf_score) / 2, 1)}%",
                "Pages Analyzed": len(getattr(crawl_obj, 'pages', [])),
                "Priority": "Fix Core Web Vitals & On-Page Issues",
            },
            "color": "#4F46E5"
        },
        "D. On-Page SEO": {
            "score": seo_score,
            "metrics": seo_res.get('metrics', {}),
            "color": "#8B5CF6"
        },
        "E. Performance": {
            "score": perf_score,
            "metrics": perf_res.get('metrics', {}),
            "color": "#10B981"
        },
        "H. Broken Links Intelligence": {
            "score": 100 if broken_count == 0 else max(30, 100 - broken_count * 4),
            "metrics": {
                "Total Broken Links": broken_count,
                "Broken Links Found": ", ".join([str(item) for item in broken_links[:3]]) if broken_links else "None",
                "Redirect Issues": 0
            },
            "color": "#F59E0B"
        }
    }

    # ────────────────────────────────────────────────
    # Real PSI integration (safe)
    # ────────────────────────────────────────────────
    psi_mobile = fetch_psi(url, 'mobile')
    psi_data = psi_mobile if psi_mobile is not None else fetch_psi(url, 'desktop')

    if psi_data is not None:
        lab = psi_data.get('lab', {})
        categories["E. Performance"]["metrics"].update({
            "LCP_ms": lab.get('lcp_ms', 'N/A'),
            "CLS": lab.get('cls', 'N/A'),
            "INP_ms": lab.get('inp_ms', 'N/A'),
            "TBT_ms": lab.get('tbt_ms', 'N/A'),
            "Speed_Index_ms": lab.get('speed_index_ms', 'N/A'),
            "TTI_ms": lab.get('tti_ms', 'N/A')
        })

        # Realistic penalty based on PSI
        lcp = lab.get('lcp_ms', 4000)
        cls = lab.get('cls', 0.25)
        tbt = lab.get('tbt_ms', 500)

        penalty = 0
        if lcp > 2500:
            penalty += (lcp - 2500) / 20
        if cls > 0.1:
            penalty += cls * 300
        if tbt > 200:
            penalty += (tbt - 200) / 5

        perf_score = max(30, perf_score - penalty)
        categories["E. Performance"]["score"] = round(perf_score, 1)
    else:
        categories["E. Performance"]["metrics"]["PSI_Status"] = "Unavailable"

    # ────────────────────────────────────────────────
    # Weighted score (performance heavier)
    # ────────────────────────────────────────────────
    weights = {
        "A. Executive Summary": 1.0,
        "D. On-Page SEO": 1.3,
        "E. Performance": 2.0,  # now heaviest
        "H. Broken Links Intelligence": 1.2
    }

    total_weight = sum(weights.values())
    weighted_sum = sum(categories[cat]["score"] * weights[cat] for cat in categories)

    overall_score = round(weighted_sum / total_weight, 2)

    # Grade
    if overall_score >= 90:
        grade = "A+"
    elif overall_score >= 80:
        grade = "A"
    elif overall_score >= 70:
        grade = "B"
    elif overall_score >= 60:
        grade = "C"
    elif overall_score >= 50:
        grade = "D"
    else:
        grade = "F"

    return {
        "url": url,
        "overall_score": overall_score,
        "grade": grade,
        "categories": categories
    }
