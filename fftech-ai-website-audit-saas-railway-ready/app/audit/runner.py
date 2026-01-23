from __future__ import annotations

import time
import statistics
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .crawler import crawl
from .grader import compute_scores  # reuse your scoring logic

HEADERS = {"User-Agent": "FFTechAuditor/1.1 (+https://fftech.ai)"}


def _normalize_url(url: str | Any) -> str:
    """Ensure URL has a scheme (default to https). Accepts str or HttpUrl."""
    url_str = str(url)  # Convert HttpUrl or any type to string
    parsed = urlparse(url_str)
    return url_str if parsed.scheme else f"https://{url_str}"


def measure_homepage_perf(url: str, attempts: int = 2, timeout: int = 10) -> Dict[str, float]:
    """
    Lightweight performance proxy using requests timing.
    """
    timings_ms: list[float] = []
    sizes_kb: list[float] = []

    for _ in range(max(1, attempts)):
        start = time.perf_counter()
        try:
            # Add verify=False to bypass SSL issues (optional; use carefully)
            r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True, verify=True)
        except requests.exceptions.SSLError:
            # fallback: ignore SSL errors
            r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True, verify=False)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        timings_ms.append(elapsed_ms)
        sizes_kb.append(len(r.content) / 1024.0)

    avg_ms = statistics.mean(timings_ms)
    p95_ms = max(timings_ms) if len(timings_ms) > 1 else timings_ms[0]
    avg_kb = statistics.mean(sizes_kb)

    return {
        "response_ms": round(avg_ms, 1),
        "response_p95_ms": round(p95_ms, 1),
        "html_kb": round(avg_kb, 1),
        "fcp_ms": round(avg_ms, 1),
        "lcp_ms": round(avg_ms * 1.6, 1),
    }


# ... (keep analyze_onpage, build_priorities, build_executive_summary unchanged)


def run_audit(url: str | Any) -> Dict[str, Any]:
    """
    REAL audit flow:
    """
    target = _normalize_url(url)

    # 1 & 2) Crawl
    cr = crawl(target, max_pages=40, timeout=10)

    # 3) On-page analysis
    onpage, onpage_details = analyze_onpage(cr.pages)

    # 4) Simple performance proxy
    perf = measure_homepage_perf(target, attempts=2, timeout=10)

    # Link metrics
    broken_internal = len(cr.broken_internal)
    broken_external = len(cr.broken_external)
    broken_total = broken_internal + broken_external
    crawl_pages_count = len(cr.pages)
    links = {"total_broken_links": broken_total}

    # 5) Score
    overall, grade, breakdown = compute_scores(
        onpage=onpage,
        perf=perf,
        links=links,
        crawl_pages_count=crawl_pages_count,
    )

    # 6) Chart/PDF/UI-friendly payload
    result: Dict[str, Any] = {
        "url": target,
        "overall_score": round(overall, 1),
        "grade": grade,
        "breakdown": breakdown,
        "performance": perf,
        "issues_overview": {
            "pages_crawled": crawl_pages_count,
            "broken_internal_links": broken_internal,
            "broken_external_links": broken_external,
            "http_status_distribution": dict(cr.status_counts),
        },
        "onpage": onpage,
        "onpage_details": onpage_details,
        "priorities": build_priorities(onpage, broken_total, perf),
        "executive_summary": build_executive_summary(
            grade=grade,
            overall=overall,
            crawl_pages=crawl_pages_count,
            broken=broken_total,
        ),
    }
    return result


__all__ = ["run_audit"]
