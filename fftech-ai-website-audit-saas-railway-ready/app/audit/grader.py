import os
from app.audit.crawler import perform_crawl
from app.audit.seo import run_seo_audit
from app.audit.performance import get_performance_metrics
from app.audit.psi import fetch_psi
from app.audit.links import check_links

# Severity weights for SEO issues
SEO_WEIGHTS = {
    "missing_title": 3,
    "duplicate_title": 2,
    "missing_h1": 2,
    "multiple_h1": 1,
    "missing_meta": 2,
    "thin_content": 1,
    "canonical_missing": 3,
    "robots_noindex": 3,
}

# Core Web Vitals thresholds
CWV_THRESHOLDS = {
    "LCP": 2500,
    "CLS": 0.1,
    "INP": 200,
    "TBT": 200
}

# Grade mapping
GRADE_MAPPING = [
    (95, "A+"),
    (85, "A"),
    (75, "B"),
    (65, "C"),
    (50, "D"),
    (0, "F")
]

def calculate_severity_score(page_metrics):
    """Calculate per-page SEO severity penalties."""
    penalties = 0
    # Titles
    penalties += page_metrics.get("41_Missing_Titles", 0) * SEO_WEIGHTS["missing_title"]
    penalties += page_metrics.get("42_Duplicate_Titles", 0) * SEO_WEIGHTS["duplicate_title"]
    # H1
    penalties += page_metrics.get("49_Missing_H1", 0) * SEO_WEIGHTS["missing_h1"]
    penalties += page_metrics.get("50_Multiple_H1", 0) * SEO_WEIGHTS["multiple_h1"]
    # Meta
    penalties += page_metrics.get("43_Missing_Meta_Descriptions", 0) * SEO_WEIGHTS["missing_meta"]
    # Content
    penalties += page_metrics.get("45_Thin_Content_Pages", 0) * SEO_WEIGHTS["thin_content"]
    # Canonical & robots
    penalties += page_metrics.get("Canonical_Missing", 0) * SEO_WEIGHTS["canonical_missing"]
    penalties += page_metrics.get("Robots_NoIndex_Pages", 0) * SEO_WEIGHTS["robots_noindex"]

    return penalties

def calculate_cwv_penalty(lcp, cls, inp, tbt):
    """Calculate Core Web Vitals penalty."""
    penalty = 0
    penalty += max(0, (lcp - CWV_THRESHOLDS["LCP"]) / 50)
    penalty += max(0, (cls - CWV_THRESHOLDS["CLS"]) * 300)
    penalty += max(0, (inp - CWV_THRESHOLDS["INP"]) / 5)
    penalty += max(0, (tbt - CWV_THRESHOLDS["TBT"]) / 5)
    return penalty

def map_grade(score):
    for threshold, grade in GRADE_MAPPING:
        if score >= threshold:
            return grade
    return "F"

def run_audit(url: str):
    """Run enterprise-grade audit on a website."""
    max_pages = int(os.getenv("MAX_CRAWL_PAGES", "50"))
    crawl_obj = perform_crawl(url, max_pages=max_pages)

    # SEO and Performance audits
    seo_res = run_seo_audit(crawl_obj)
    perf_res = get_performance_metrics(url)

    # Broken links
    broken_links = getattr(crawl_obj, 'broken_internal', [])
    broken_count = len(broken_links)

    # Per-page SEO penalty
    seo_penalty = calculate_severity_score(seo_res.get("metrics", {}))
    seo_score = max(0, 100 - (seo_penalty / max(1, len(getattr(crawl_obj, 'pages', [])))))

    # Core Web Vitals penalty
    psi_mobile = fetch_psi(url, "mobile")
    psi_data = psi_mobile or fetch_psi(url, "desktop")
    cwv_penalty = 0
    cwv_metrics = {}
    if psi_data:
        lab = psi_data.get("lab", {})
        lcp = lab.get("lcp_ms", 4000)
        cls = lab.get("cls", 0.25)
        inp = lab.get("inp_ms", 300)
        tbt = lab.get("tbt_ms", 500)
        cwv_penalty = calculate_cwv_penalty(lcp, cls, inp, tbt)
        cwv_metrics.update({"LCP_ms": lcp, "CLS": cls, "INP_ms": inp, "TBT_ms": tbt})
    else:
        cwv_metrics["PSI_Status"] = "Unavailable"

    perf_score = max(0, perf_res.get("score", 50) - cwv_penalty)

    # Broken links impact
    broken_score = max(0, 100 - broken_count * 4)

    # Weighted overall score
    weights = {
        "seo": 0.4,
        "performance": 0.5,
        "broken": 0.1
    }
    overall_score = (
        seo_score * weights["seo"] +
        perf_score * weights["performance"] +
        broken_score * weights["broken"]
    )

    grade = map_grade(overall_score)

    # Categories output
    categories = {
        "A. Executive Summary": {
            "score": round(overall_score, 1),
            "metrics": {
                "Overall Health": f"{round(overall_score, 1)}%",
                "Pages Analyzed": len(getattr(crawl_obj, 'pages', [])),
                "Priority": "Fix Core Web Vitals & On-Page Issues",
            },
            "color": "#4F46E5"
        },
        "D. On-Page SEO": {
            "score": round(seo_score, 1),
            "metrics": seo_res.get("metrics", {}),
            "color": "#8B5CF6"
        },
        "E. Performance": {
            "score": round(perf_score, 1),
            "metrics": {**perf_res.get("metrics", {}), **cwv_metrics},
            "color": "#10B981"
        },
        "H. Broken Links Intelligence": {
            "score": round(broken_score, 1),
            "metrics": {
                "Total Broken Links": broken_count,
                "Broken Links Found": ", ".join([str(item) for item in broken_links[:3]]) if broken_links else "None",
            },
            "color": "#F59E0B"
        },
        "I. AI Recommendations": {
            "score": None,
            "metrics": {"note": "AI suggestions can be integrated here"},
            "color": "#3B82F6"
        }
    }

    return {
        "url": url,
        "overall_score": round(overall_score, 2),
        "grade": grade,
        "categories": categories
    }
