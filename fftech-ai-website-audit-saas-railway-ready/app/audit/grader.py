import time
import os
from app.audit.crawler import perform_crawl
from app.audit.seo import run_seo_audit
from app.audit.performance import get_performance_metrics
from app.audit.psi import fetch_psi
from app.audit.links import check_links
from app.audit.ai_recommendations import generate_ai_recommendations
from app.audit.page_diagnostics import per_page_diagnostics
from app.audit.sitemap import crawl_sitemap


def run_audit(url: str):
    """
    World-class website audit orchestrator:
    - Preserves input/output links
    - Integrates SEO + Performance + AI recommendations
    - Page-level diagnostics
    - JS Rendering & Sitemap integration
    """

    # --------------------------
    # 1. Crawl site
    # --------------------------
    max_pages = int(os.getenv("MAX_CRAWL_PAGES", "50"))
    crawl_obj = perform_crawl(url, max_pages=max_pages)

    # --------------------------
    # 2. Run SEO & Performance
    # --------------------------
    seo_res = run_seo_audit(crawl_obj)
    perf_res = get_performance_metrics(url)

    # --------------------------
    # 3. Broken Links
    # --------------------------
    broken_links = getattr(crawl_obj, 'broken_internal', [])
    broken_count = len(broken_links)

    # --------------------------
    # 4. Page-level diagnostics
    # --------------------------
    page_diags = per_page_diagnostics(getattr(crawl_obj, 'pages', []))
    for p in page_diags:
        # Detect JS-heavy pages (lightweight)
        html_size = p.get("word_count", 0)
        script_count = len([s for s in getattr(crawl_obj, 'pages', []) if p["url"] in s.get("url", "") and s.get("word_count", 0) > 0])
        p["JS_Rendering_Detected"] = html_size < 2000 and script_count > 10

    # --------------------------
    # 5. Sitemap URLs (optional discovery)
    # --------------------------
    sitemap_urls = crawl_sitemap(url)

    # --------------------------
    # 6. Compute base scores
    # --------------------------
    seo_score = seo_res.get('score', 70.0)
    perf_score = perf_res.get('score', 65.0)

    # Adjust performance score based on PSI lab if available
    psi_mobile = fetch_psi(url, 'mobile')
    psi_data = psi_mobile if psi_mobile is not None else fetch_psi(url, 'desktop')
    if psi_data:
        lab = psi_data.get('lab', {}) or {}
        perf_res["metrics"].update({
            "LCP_ms": lab.get('lcp_ms', 'N/A'),
            "CLS": lab.get('cls', 'N/A'),
            "INP_ms": lab.get('inp_ms', 'N/A'),
            "TBT_ms": lab.get('tbt_ms', 'N/A')
        })

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
        perf_res["score"] = round(perf_score, 1)
    else:
        perf_res["metrics"]["PSI_Status"] = "Unavailable"

    # --------------------------
    # 7. Categories
    # --------------------------
    categories = {
        "A. Executive Summary": {
            "score": round((seo_score + perf_score) / 2, 1),
            "metrics": {
                "Overall Health": f"{round((seo_score + perf_score) / 2, 1)}%",
                "Pages Analyzed": len(getattr(crawl_obj, 'pages', [])),
                "Priority": "Fix Core Web Vitals & On-Page Issues",
                "Sitemap_Discovered_URLs": len(sitemap_urls)
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

    # --------------------------
    # 8. AI Recommendations
    # --------------------------
    ai_recs = generate_ai_recommendations(categories.get("D. On-Page SEO", {}).get("metrics", {}),
                                          categories.get("E. Performance", {}).get("metrics", {}))
    categories["I. AI Recommendations"] = {
        "score": None,
        "metrics": {"Recommendations": ai_recs},
        "color": "#0EA5E9"
    }

    # --------------------------
    # 9. Weighted overall score
    # --------------------------
    weights = {
        "A. Executive Summary": 1.0,
        "D. On-Page SEO": 1.3,
        "E. Performance": 2.0,
        "H. Broken Links Intelligence": 1.2
    }

    total_weight = sum(weights.values())
    weighted_sum = sum(categories[cat]["score"] * weights[cat] for cat in weights)
    overall_score = round(weighted_sum / total_weight, 2)

    # --------------------------
    # 10. Grade Assignment
    # --------------------------
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

    # --------------------------
    # 11. Return final audit
    # --------------------------
    return {
        "url": url,
        "overall_score": float(overall_score) if overall_score is not None else 0.0,
        "grade": grade or "F",
        "categories": categories or {},
        "page_diagnostics": page_diags,
        "sitemap_urls": sitemap_urls
    }
