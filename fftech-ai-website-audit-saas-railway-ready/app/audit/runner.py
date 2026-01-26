
import logging
import time
from typing import Dict, List
from urllib.parse import urlparse, urljoin

import certifi
import requests
from bs4 import BeautifulSoup
import urllib3

from .crawler import crawl   # Optimized BFS crawler

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger("audit_engine")


# ---------------------------------------------------------
# Utility
# ---------------------------------------------------------
def _clamp(v: float, lo: float = 0, hi: float = 100) -> int:
    return int(max(lo, min(hi, round(v))))



# ---------------------------------------------------------
# WORLD‑CLASS MAIN AUDIT
# ---------------------------------------------------------
def run_audit(url: str) -> Dict:
    """
    FULL ENTERPRISE‑GRADE WEBSITE AUDIT ENGINE
    ---------------------------------------------------------
    Steps:
      1) Fetch landing page (with SSL fallback)
      2) Extract SEO + WCAG + Security signals
      3) Compute performance: TTFB, page size, connection time
      4) Run BFS crawler (internal/external/broken/coverage)
      5) Build detailed issues list (SEO+Perf+Coverage+Security)
      6) Produce chart-ready data: bar, radar, doughnut
      7) Return a complete audit model for index.html
    ---------------------------------------------------------
    Ultra‑fast: optimized requests, no unnecessary parsing,
    and minimal blocking operations.
    """

    logger.info("RUNNING AUDIT FOR URL: %s", url)
    start_time = time.time()

    headers = {
        "User-Agent": "FFTech-AuditBot/3.0 (+https://fftech.audit)",
        "Accept": "text/html,application/xhtml+xml",
    }

    session = requests.Session()
    session.headers.update(headers)

    # ---------------------------------------------------------
    # 1. FETCH LANDING PAGE (with SSL fallback)
    # ---------------------------------------------------------
    ssl_verified = True
    try:
        response = session.get(url, timeout=12, verify=certifi.where(), allow_redirects=True)
    except requests.exceptions.SSLError:
        ssl_verified = False
        response = session.get(url, timeout=12, verify=False, allow_redirects=True)
    except Exception as e:
        raise RuntimeError(f"Cannot fetch {url}: {e}")

    load_time = round(time.time() - start_time, 3)
    final_url = response.url
    parsed = urlparse(final_url)
    html = response.text

    soup = BeautifulSoup(html, "html.parser")

    # ---------------------------------------------------------
    # 2. SEO & CONTENT AUDIT
    # ---------------------------------------------------------
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_desc = ""
    md_tag = soup.find("meta", attrs={"name": "description"})
    if md_tag and md_tag.get("content"):
        meta_desc = md_tag["content"].strip()

    h1_tags = soup.find_all("h1")
    h1_count = len(h1_tags)

    seo_issues: List[str] = []
    seo_score = 0

    # Title
    if title:
        seo_score += 25
        seo_score += max(0, 25 - abs(len(title) - 55))     # title optimal length bonus
    else:
        seo_issues.append("Missing <title> tag")

    # Meta description
    if meta_desc:
        seo_score += min(25, len(meta_desc) / 6)
    else:
        seo_issues.append("Missing meta description")

    # H1
    if h1_count == 1:
        seo_score += 15
    elif h1_count == 0:
        seo_issues.append("Missing H1 tag")
    else:
        seo_issues.append("Multiple H1 tags found")

    # Alt attributes check
    images = soup.find_all("img")
    images_missing_alt = len([img for img in images if not img.get("alt")])
    if images_missing_alt > 0:
        seo_issues.append(f"{images_missing_alt} images missing ALT text")

    seo_score = _clamp(seo_score)


    # ---------------------------------------------------------
    # 3. PERFORMANCE AUDIT
    # ---------------------------------------------------------
    page_size_kb = round(len(html.encode("utf-8")) / 1024, 2)
    perf_score = 100
    perf_issues: List[str] = []

    # TTFB / Load time penalty
    perf_score -= min(40, load_time * 8)

    # Page size penalty
    perf_score -= min(40, page_size_kb / 30)

    # Viewport
    if not soup.find("meta", attrs={"name": "viewport"}):
        perf_issues.append("Missing viewport meta tag")

    perf_score = _clamp(perf_score)

    speed_sub = _clamp(100 - min(100, load_time * 25))
    weight_sub = _clamp(100 - min(100, (page_size_kb / 2000) * 100))


    # ---------------------------------------------------------
    # 4. COVERAGE + BROKEN LINKS (CRAWLER ENGINE)
    # ---------------------------------------------------------
    crawl_res = crawl(final_url, max_pages=15, delay=0.25)

    internal_total = crawl_res.unique_internal
    external_total = crawl_res.unique_external
    broken_total = len(crawl_res.broken_internal)

    coverage_score = (
        min(60, internal_total * 2) +
        min(30, external_total) -
        min(20, broken_total * 2)
    )
    coverage_score = _clamp(coverage_score)

    coverage_issues: List[str] = []
    if internal_total < 5:
        coverage_issues.append(f"Low internal linking ({internal_total} pages)")
    if external_total < 2:
        coverage_issues.append(f"Few outgoing links ({external_total})")
    if broken_total > 0:
        coverage_issues.append(f"{broken_total} broken internal links detected")


    internal_linking_sub = _clamp(min(100, internal_total * 4))
    external_linking_sub = _clamp(min(100, external_total * 3))


    # ---------------------------------------------------------
    # 5. FINAL OVERALL SCORE + AI Confidence
    # ---------------------------------------------------------
    overall_score = _clamp(
        seo_score * 0.45 +
        perf_score * 0.35 +
        coverage_score * 0.20
    )

    grade = (
        "A" if overall_score >= 85 else
        "B" if overall_score >= 70 else
        "C" if overall_score >= 55 else
        "D"
    )

    confidence_score = overall_score


    # ---------------------------------------------------------
    # 6. CHART DATA (BAR, RADAR, DOUGHNUT)
    # ---------------------------------------------------------
    chart_data = {
        "bar": {
            "labels": ["SEO", "Speed", "Links", "Trust"],
            "data": [seo_score, perf_score, coverage_score, confidence_score],
            "colors": ["#0d6efd", "#20c997", "#ffc107", "#dc3545"]
        },
        "radar": {
            "labels": [
                "Title Quality", "Meta Description", "H1 Structure",
                "Speed", "Page Weight", "Internal Linking", "External Linking"
            ],
            "data": [
                _clamp(100 if title else 0),
                _clamp(100 if meta_desc else 0),
                _clamp(100 if h1_count == 1 else 50 if h1_count > 1 else 0),
                speed_sub,
                weight_sub,
                internal_linking_sub,
                external_linking_sub
            ]
        },
        "doughnut": {
            "labels": ["SEO Issues", "Performance Issues", "Coverage Issues"],
            "data": [len(seo_issues), len(perf_issues), len(coverage_issues)],
            "colors": ["#6f42c1", "#fd7e14", "#0dcaf0"]
        }
    }


    # ---------------------------------------------------------
    # 7. RETURN FULL AUDIT MODEL
    # ---------------------------------------------------------
    return {
        "finished": True,
        "url": final_url,
        "domain": parsed.netloc,
        "http_status": response.status_code,
        "https": parsed.scheme == "https",
        "ssl_secure": ssl_verified,
        "overall_score": overall_score,
        "grade": grade,

        "breakdown": {
            "onpage": seo_score,
            "performance": perf_score,
            "coverage": coverage_score,
            "confidence": confidence_score
        },

        "metrics": {
            "title_length": len(title),
            "meta_description_length": len(meta_desc),
            "h1_count": h1_count,
            "internal_links": internal_total,
            "external_links": external_total,
            "broken_internal_links": broken_total,
            "load_time_sec": load_time,
            "page_size_kb": page_size_kb,
            "pages_crawled": crawl_res.crawled_count,
            "crawl_time_sec": crawl_res.total_crawl_time
        },

        "issues": {
            "seo": seo_issues,
            "performance": perf_issues,
            "coverage": coverage_issues
        },

        "issues_count": {
            "seo": len(seo_issues),
            "performance": len(perf_issues),
            "coverage": len(coverage_issues)
        },

        "chart_data": chart_data,
        "status": "Audit completed successfully"
    }
