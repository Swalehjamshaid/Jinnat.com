
# app/audit/runner.py

import logging
import time
from typing import Dict
from urllib.parse import urlparse, urljoin

import certifi
import requests
from bs4 import BeautifulSoup
import urllib3

# Disable SSL warnings globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("audit_engine")


def run_audit(url: str) -> Dict:
    """
    Performs a realistic audit per website.
    Returns a structured dictionary with scores, metrics, and breakdown.
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

    # ───────────── SEO SCORING ─────────────
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc_tag["content"].strip() if meta_desc_tag and meta_desc_tag.get("content") else ""

    seo_score = 0
    # Title scoring
    if title:
        seo_score += 25
        seo_score += max(0, 25 - abs(len(title) - 55))  # optimal length bonus
    # Meta description scoring
    if meta_desc:
        seo_score += min(25, len(meta_desc) / 6)
    # H1 scoring
    h1_count = len(soup.find_all("h1"))
    seo_score += 15 if h1_count == 1 else 5 if h1_count > 1 else 0
    seo_score = min(100, round(seo_score))

    # ───────────── PERFORMANCE SCORING ─────────────
    page_size_kb = round(len(html.encode("utf-8")) / 1024, 2)
    perf_score = 100
    perf_score -= min(40, load_time * 8)        # penalty for slow pages
    perf_score -= min(40, page_size_kb / 30)    # penalty for large pages
    perf_score = max(0, round(perf_score))

    # ───────────── LINK COVERAGE SCORING ─────────────
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
    coverage_score = round(min(100, coverage_score))

    # ───────────── FINAL SCORING ─────────────
    overall_score = round(
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

    # NEW: Confidence — keep it simple by mirroring overall score (0–100)
    # You can later replace this with a custom trust metric if desired.
    confidence_score = overall_score

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
            "confidence": confidence_score,  # <-- added for the Trust tile
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
        "status": "Audit completed successfully",
    }
