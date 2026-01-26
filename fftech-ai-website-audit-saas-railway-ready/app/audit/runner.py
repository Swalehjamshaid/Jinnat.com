# app/audit/runner.py
import logging
import time
from typing import Dict, List
from urllib.parse import urlparse
import certifi
import requests
from bs4 import BeautifulSoup
import urllib3
from .crawler import crawl

# Disable SSL warnings globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger('audit_engine')


def _clamp(v: float, lo: float = 0, hi: float = 100) -> int:
    return int(max(lo, min(hi, round(v))))


def run_audit(url: str) -> Dict:
    """
    World-class Single-URL Audit
    Returns dict compatible with index.html (metrics + charts)
    """
    logger.info("RUNNING AUDIT FOR URL: %s", url)
    start_time = time.time()
    headers = {'User-Agent': 'FFTech-AuditBot/4.0 (+https://fftech.audit)'}
    session = requests.Session()
    session.headers.update(headers)

    ssl_verified = True
    try:
        response = session.get(url, timeout=20, verify=certifi.where(), allow_redirects=True)
    except requests.exceptions.SSLError:
        ssl_verified = False
        response = session.get(url, timeout=20, verify=False, allow_redirects=True)
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch URL {url}: {e}")

    load_time = round(time.time() - start_time, 2)
    final_url = response.url
    parsed = urlparse(final_url)
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    # ---------- SEO Metrics ----------
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc_tag["content"].strip() if meta_desc_tag and meta_desc_tag.get("content") else ""
    h1_tags = soup.find_all("h1")
    h1_count = len(h1_tags)

    img_tags = soup.find_all("img")
    missing_alt = sum(1 for img in img_tags if not img.get("alt"))

    seo_issues: List[str] = []
    seo_score = 0.0

    # Title
    if title:
        seo_score += 25
        seo_score += max(0, 25 - abs(len(title) - 55))
        if len(title) < 25:
            seo_issues.append("Title very short")
        elif len(title) > 65:
            seo_issues.append("Title too long")
    else:
        seo_issues.append("Missing <title>")

    # Meta
    if meta_desc:
        seo_score += min(25, len(meta_desc) / 6)
        if len(meta_desc) < 80:
            seo_issues.append("Meta description too short")
        elif len(meta_desc) > 180:
            seo_issues.append("Meta description too long")
    else:
        seo_issues.append("Missing meta description")

    # H1
    if h1_count == 1:
        seo_score += 15
    elif h1_count == 0:
        seo_issues.append("No H1 tag")
    else:
        seo_issues.append(f"Multiple H1 tags ({h1_count})")

    # Images
    if missing_alt:
        seo_issues.append(f"{missing_alt} images missing alt attribute")

    seo_score = _clamp(seo_score)

    # ---------- Performance ----------
    page_size_kb = round(len(html.encode("utf-8")) / 1024, 2)
    perf_issues: List[str] = []
    perf_score = 100
    perf_score -= min(40, load_time * 8)
    perf_score -= min(40, page_size_kb / 30)
    perf_score = _clamp(perf_score)

    if load_time > 3:
        perf_issues.append(f"Slow load ({load_time}s)")
    if page_size_kb > 2000:
        perf_issues.append(f"Page too large ({page_size_kb} KB)")

    # Radar sub-metrics
    speed_sub = _clamp(100 - min(100, load_time * 25))
    weight_sub = _clamp(100 - min(100, (page_size_kb / 2000) * 100))

    # ---------- Crawl & Link Coverage ----------
    crawl_res = crawl(final_url, max_pages=50, delay=0.2)
    internal_total = crawl_res.unique_internal
    external_total = crawl_res.unique_external
    broken_count = len(crawl_res.broken_internal)

    coverage_base = min(60, internal_total * 2) + min(30, external_total)
    broken_penalty = min(20, broken_count * 2)
    coverage_score = _clamp(coverage_base - broken_penalty)

    coverage_issues: List[str] = []
    if internal_total < 5:
        coverage_issues.append(f"Low internal links ({internal_total})")
    if external_total < 2:
        coverage_issues.append(f"Low external links ({external_total})")
    if broken_count > 0:
        coverage_issues.append(f"Broken internal links: {broken_count}")

    internal_linking_sub = _clamp(min(100, internal_total * 5))
    external_linking_sub = _clamp(min(100, external_total * 3))

    # ---------- Overall Score ----------
    overall_score = _clamp(seo_score * 0.45 + perf_score * 0.35 + coverage_score * 0.2)
    grade = "A" if overall_score >= 85 else "B" if overall_score >= 70 else "C" if overall_score >= 55 else "D"
    confidence_score = overall_score

    # ---------- Chart Data ----------
    chart_data = {
        "bar": {
            "labels": ["SEO", "Speed", "Links", "Confidence", "Images", "Meta"],
            "data": [
                seo_score, perf_score, coverage_score, confidence_score,
                _clamp(100 - missing_alt), _clamp(len(meta_desc))
            ],
            "colors": ["#0d6efd", "#20c997", "#ffc107", "#dc3545", "#6f42c1", "#fd7e14"]
        },
        "radar": {
            "labels": [
                "Title Quality", "Meta Description", "H1 Structure",
                "Speed", "Page Weight", "Internal Links", "External Links",
                "Alt Attributes"
            ],
            "data": [
                _clamp(100 if title else 0),
                _clamp(100 if meta_desc else 0),
                _clamp(100 if h1_count == 1 else 50 if h1_count > 1 else 0),
                speed_sub,
                weight_sub,
                internal_linking_sub,
                external_linking_sub,
                _clamp(100 - missing_alt)
            ]
        },
        "doughnut": {
            "labels": ["SEO issues", "Performance issues", "Links issues", "Images issues"],
            "data": [len(seo_issues), len(perf_issues), len(coverage_issues), missing_alt],
            "colors": ["#6f42c1", "#fd7e14", "#0dcaf0", "#6610f2"]
        },
        "crawl": {
            "status_counts": dict(crawl_res.status_counts),
            "internal_total": internal_total,
            "external_total": external_total,
            "broken_internal": broken_count
        }
    }

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
            "broken_internal_links": broken_count,
            "load_time_sec": load_time,
            "page_size_kb": page_size_kb,
            "pages_crawled": crawl_res.crawled_count,
            "crawl_time_sec": crawl_res.total_crawl_time,
            "images_missing_alt": missing_alt
        },
        "issues": {
            "seo": seo_issues,
            "performance": perf_issues,
            "coverage": coverage_issues
        },
        "issues_count": {
            "seo": len(seo_issues),
            "performance": len(perf_issues),
            "coverage": len(coverage_issues),
            "images": missing_alt
        },
        "chart_data": chart_data,
        "status": "Audit completed successfully"
    }
