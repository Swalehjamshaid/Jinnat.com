# app/audit/runner.py
import logging, time
from typing import Dict
from urllib.parse import urlparse
import certifi, requests
from bs4 import BeautifulSoup
import urllib3
from .crawler import crawl

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger('audit_engine')


def _clamp(v: float, lo: float = 0, hi: float = 100) -> int:
    """Clamp score between 0 and 100"""
    return int(max(lo, min(hi, round(v))))


def run_audit(url: str) -> Dict:
    """
    World-Class Audit Engine (International Standards)
    """
    logger.info("RUNNING AUDIT FOR URL: %s", url)
    start_time = time.time()

    # ---------------- HTTP REQUEST ----------------
    headers = {'User-Agent': 'IntlAuditBot/1.0', 'Accept': 'text/html,application/xhtml+xml'}
    session = requests.Session()
    session.headers.update(headers)

    ssl_verified = True
    try:
        response = session.get(url, timeout=10, verify=certifi.where(), allow_redirects=True)
    except requests.exceptions.SSLError:
        ssl_verified = False
        response = session.get(url, timeout=10, verify=False, allow_redirects=True)
    except Exception as e:
        raise RuntimeError(f"Cannot fetch URL {url}: {e}")

    load_time = round(time.time() - start_time, 2)
    final_url = response.url
    parsed = urlparse(final_url)
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    # ---------------- SEO ----------------
    title = soup.title.string.strip() if soup.title else ""
    meta_desc = (soup.find("meta", {"name": "description"}) or {}).get("content", "").strip()
    h1_tags = soup.find_all("h1")
    h1_count = len(h1_tags)
    img_tags = soup.find_all("img")
    missing_alt = sum(1 for img in img_tags if not img.get("alt"))
    canonical_tag = (soup.find("link", {"rel": "canonical"}) or {}).get("href", "")

    seo_score = 0
    seo_issues = []

    # Title
    if title:
        seo_score += 20
        if 50 <= len(title) <= 60:
            seo_score += 5
        else:
            seo_issues.append("Title length not optimal")
    else:
        seo_issues.append("Missing title")

    # Meta Description
    if meta_desc:
        seo_score += 15
        if 120 <= len(meta_desc) <= 160:
            seo_score += 5
        else:
            seo_issues.append("Meta description length not optimal")
    else:
        seo_issues.append("Missing meta description")

    # H1
    if h1_count == 1:
        seo_score += 15
    elif h1_count == 0:
        seo_issues.append("No H1 tag")
    else:
        seo_issues.append(f"{h1_count} H1 tags")

    # Images
    if missing_alt == 0:
        seo_score += 10
    else:
        seo_issues.append(f"{missing_alt} images missing alt")

    # Canonical
    if canonical_tag:
        seo_score += 5
    else:
        seo_issues.append("Missing canonical tag")

    seo_score = _clamp(seo_score)

    # ---------------- PERFORMANCE ----------------
    page_size_kb = round(len(html.encode("utf-8")) / 1024, 2)
    perf_score = 100
    perf_score -= min(40, load_time * 8)
    perf_score -= min(40, page_size_kb / 30)
    perf_score = _clamp(perf_score)
    perf_issues = []
    if load_time > 3:
        perf_issues.append(f"Slow load time: {load_time}s")
    if page_size_kb > 2000:
        perf_issues.append(f"Large page size: {page_size_kb} KB")

    # ---------------- LINKS & COVERAGE ----------------
    crawl_res = crawl(final_url, max_pages=10, delay=0.01)
    internal_total = crawl_res.unique_internal
    external_total = crawl_res.unique_external
    broken_count = len(crawl_res.broken_internal)

    coverage_score = _clamp(min(60, internal_total * 3) + min(20, external_total * 2) - min(20, broken_count * 2))
    coverage_issues = []
    if internal_total < 5:
        coverage_issues.append(f"Low internal links: {internal_total}")
    if broken_count > 0:
        coverage_issues.append(f"Broken internal links: {broken_count}")

    # ---------------- OVERALL ----------------
    overall_score = _clamp(seo_score * 0.4 + perf_score * 0.35 + coverage_score * 0.25)
    grade = "A" if overall_score >= 85 else "B" if overall_score >= 70 else "C" if overall_score >= 55 else "D"

    return {
        "finished": True,
        "url": final_url,
        "domain": parsed.netloc,
        "https": parsed.scheme == "https",
        "ssl_secure": ssl_verified,
        "overall_score": overall_score,
        "grade": grade,
        "seo_score": seo_score,
        "performance_score": perf_score,
        "coverage_score": coverage_score,
        "issues": {
            "seo": seo_issues,
            "performance": perf_issues,
            "coverage": coverage_issues
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
            "images_missing_alt": missing_alt
        },
        "status": "Audit completed successfully"
    }
