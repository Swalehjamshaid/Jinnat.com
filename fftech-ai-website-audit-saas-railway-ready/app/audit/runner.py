# app/audit/runner.py (or wherever run_audit lives)

import logging
import time
from typing import Dict
from urllib.parse import urlparse, urljoin

import certifi
import requests
from bs4 import BeautifulSoup
import urllib3

# Suppress insecure request warnings globally (safe since we handle SSL explicitly)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("audit_engine")


def run_audit(url: str) -> Dict:
    """
    Perform a lightweight website audit focusing on SEO, performance, and link structure.
    Preserves original input/output contract exactly.
    """
    start_time = time.time()
    headers = {
        "User-Agent": "FFTech-AuditBot/2.1 (+https://fftech.audit)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    session = requests.Session()
    session.headers.update(headers)

    # Try secure connection first
    ssl_verified = True
    try:
        response = session.get(url, timeout=20, verify=certifi.where())
    except requests.exceptions.SSLError:
        logger.warning("SSL error on %s – falling back to unverified", url)
        ssl_verified = False
        response = session.get(url, timeout=20, verify=False)
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch URL: {e}")

    load_time = round(time.time() - start_time, 2)
    final_url = response.url
    parsed = urlparse(final_url)
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    # ───────────────────── SEO ANALYSIS ─────────────────────
    title_tag = soup.title
    title = title_tag.string.strip() if title_tag and title_tag.string else ""
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc_tag["content"].strip() if meta_desc_tag and meta_desc_tag.get("content") else ""

    seo_score = 0
    if title:
        seo_score += 40
        if len(title) <= 60:
            seo_score += 20
    if meta_desc:
        seo_score += 40

    # ───────────────────── PERFORMANCE ─────────────────────
    page_size_kb = round(len(html.encode("utf-8")) / 1024, 2)
    perf_score = 100
    if page_size_kb > 500:
        perf_score -= 30
    if load_time > 3:
        perf_score -= 30
    perf_score = max(perf_score, 40)

    # ───────────────────── LINK COVERAGE ─────────────────────
    internal_links = external_links = 0
    base_domain = parsed.netloc

    for a in soup.find_all("a", href=True):
        absolute_link = urljoin(final_url, a["href"])
        link_domain = urlparse(absolute_link).netloc
        if link_domain == base_domain:
            internal_links += 1
        elif link_domain:
            external_links += 1

    coverage_score = min(100, internal_links * 5 + 20)

    # ───────────────────── SCORING ─────────────────────
    confidence = round((seo_score + perf_score + coverage_score) / 3)

    overall_score = round(
        seo_score * 0.4 +
        perf_score * 0.35 +
        coverage_score * 0.25
    )

    grade = "A" if overall_score >= 85 else "B" if overall_score >= 70 else "C" if overall_score >= 55 else "D"

    # ───────────────────── RETURN SAME STRUCTURE ─────────────────────
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
            "confidence": confidence,
        },
        "metrics": {
            "title_present": bool(title),
            "meta_description_present": bool(meta_desc),
            "internal_links": internal_links,
            "external_links": external_links,
            "load_time_sec": load_time,
            "page_size_kb": page_size_kb,
        },
        "status": "Audit completed successfully",
    }
