
# app/audit/runner.py

import logging
import time
from typing import Dict, List
from urllib.parse import urlparse, urljoin

import certifi
import requests
from bs4 import BeautifulSoup
import urllib3

# Disable SSL warnings globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("audit_engine")


def _clamp(v: float, lo: float = 0, hi: float = 100) -> int:
    return int(max(lo, min(hi, round(v))))


def run_audit(url: str) -> Dict:
    """
    Performs a realistic audit per website.
    Returns a structured dictionary with scores, metrics, breakdown, issues, and chart-ready data.
    """
    logger.info("RUNNING AUDIT FOR URL: %s", url)
    start_time = time.time()

    headers = {
        "User-Agent": "FFTech-AuditBot/2.1 (+https://fftech.audit)",
        "Accept": "text/html,application/xhtml+xml",
    }

    session = requests.Session()
    session.headers.update(headers)

    ssl_verified = True
    try:
        response = session.get(url, timeout=20, verify=certifi.where())
    except requests.exceptions.SSLError:
        logger.warning("SSL error on %s – falling back to unverified.", url)
        ssl_verified = False
        response = session.get(url, timeout=20, verify=False)
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch URL {url}: {e}")

    load_time = round(time.time() - start_time, 2)
    final_url = response.url
    parsed = urlparse(final_url)
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    # ───────────── SEO SCORING + ISSUES ─────────────
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc_tag["content"].strip() if meta_desc_tag and meta_desc_tag.get("content") else ""
    h1_tags = soup.find_all("h1")
    h1_count = len(h1_tags)

    seo_issues: List[str] = []
    seo_score = 0

    # Title presence + length quality (target ~55 chars)
    if title:
        seo_score += 25
        title_bonus = max(0.0, 25 - abs(len(title) - 55))
        seo_score += title_bonus
        if len(title) < 25:
            seo_issues.append("Title is very short (<25 chars)")
        elif len(title) > 65:
            seo_issues.append("Title is long (>65 chars)")
    else:
        seo_issues.append("Missing <title> tag")

    # Meta description presence + approximate length quality (target 120–160)
    if meta_desc:
        seo_score += min(25.0, len(meta_desc) / 6.0)
        if len(meta_desc) < 80:
            seo_issues.append("Meta description is short (<80 chars)")
        elif len(meta_desc) > 180:
            seo_issues.append("Meta description is long (>180 chars)")
    else:
        seo_issues.append("Missing meta description")

    # H1
    if h1_count == 1:
        seo_score += 15
    elif h1_count == 0:
        seo_issues.append("No H1 tag found")
    else:
        seo_issues.append("Multiple H1 tags found")

    seo_score = _clamp(seo_score)

    # ───────────── PERFORMANCE SCORING + ISSUES ─────────────
    page_size_kb = round(len(html.encode("utf-8")) / 1024, 2)
    perf_issues: List[str] = []

    perf_score = 100
    perf_score -= min(40, load_time * 8)        # penalty for slow pages
    perf_score -= min(40, page_size_kb / 30)    # penalty for large pages
    perf_score = _clamp(perf_score)

    if load_time > 3.0:
        perf_issues.append(f"Slow page load ({load_time}s > 3s)")
    if page_size_kb > 2000:
        perf_issues.append(f"Large page size ({page_size_kb} KB > 2000 KB)")

    # Sub-metrics (for radar)
    speed_sub = _clamp(100 - min(100, load_time * 25))        # 4s ⇒ ~0
    weight_sub = _clamp(100 - min(100, (page_size_kb / 2000) * 100))  # 2000KB ⇒ 0

    # ───────────── COVERAGE (LINKS) + ISSUES ─────────────
    internal_links = external_links = 0
    base_domain = parsed.netloc

    for a in soup.find_all("a", href=True):
        link = urljoin(final_url, a["href"])
        domain = urlparse(link).netloc
        if domain == base_domain:
            internal_links += 1
        elif domain:
            external_links += 1

    coverage_score = 0
    coverage_score += min(60, internal_links * 2)
    coverage_score += min(40, external_links)
    coverage_score = _clamp(coverage_score)

    coverage_issues: List[str] = []
    if internal_links < 5:
        coverage_issues.append(f"Low internal links ({internal_links} < 5)")
    if external_links < 2:
        coverage_issues.append(f"Low external links ({external_links} < 2)")

    # Sub-metrics (for radar)
    internal_linking_sub = _clamp(min(100, internal_links * 5))  # 20 internal ⇒ 100
    external_linking_sub = _clamp(min(100, external_links * 3))  # 34 external ⇒ 100

    # ───────────── FINAL SCORING + CONFIDENCE ─────────────
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

    # Confidence: keep simple for UI (match tile), can be replaced by a trust model later
    confidence_score = overall_score

    # ───────────── Chart-ready payload ─────────────
    chart_data = {
        "bar": {
            "labels": ["SEO", "Speed", "Links", "Trust"],
            "data": [seo_score, perf_score, coverage_score, confidence_score],
            "colors": ["#0d6efd", "#20c997", "#ffc107", "#dc3545"],
        },
        "radar": {
            "labels": [
                "Title Quality", "Meta Description", "H1 Structure",
                "Speed", "Page Weight", "Internal Linking", "External Linking"
            ],
            "data": [
                # For "Title Quality" & "Meta Description" & "H1 Structure", derive simple subs:
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
            "labels": ["SEO issues", "Performance issues", "Links issues"],
            "data": [
                len(seo_issues),
                len(perf_issues),
                len(coverage_issues)
            ],
            "colors": ["#6f42c1", "#fd7e14", "#0dcaf0"]
        }
    }

    return {
        "finished": True,
        "url": final_url,
        "domain": base_domain,
        "http_status": response.status_code,
        "https": parsed.scheme == "https",
        "ssl_secure": ssl_verified,
        "overall_score": overall_score,
        "grade": grade,
        "breakdown": {
            "onpage": seo_score,
            "performance": perf_score,
            "coverage": coverage_score,
            "confidence": confidence_score,
        },
        "metrics": {
            "title_length": len(title),
            "meta_description_length": len(meta_desc),
            "h1_count": h1_count,
            "internal_links": internal_links,
            "external_links": external_links,
            "load_time_sec": load_time,
            "page_size_kb": page_size_kb,
        },
        "issues": {
            "seo": seo_issues,
            "performance": perf_issues,
            "coverage": coverage_issues,
        },
        "issues_count": {
            "seo": len(seo_issues),
            "performance": len(perf_issues),
            "coverage": len(coverage_issues),
        },
        "chart_data": chart_data,
        "status": "Audit completed successfully",
    }
