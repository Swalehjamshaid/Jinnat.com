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
    """Ensure URL has a scheme (default to https). Handles Pydantic HttpUrl objects."""
    url_str = str(url)  # Convert HttpUrl to string if needed
    parsed = urlparse(url_str)
    return url_str if parsed.scheme else f"https://{url_str}"


def measure_homepage_perf(url: str, attempts: int = 2, timeout: int = 10) -> Dict[str, float]:
    """
    Lightweight performance proxy using requests timing.
    Not a replacement for Lighthouse, but gives real, repeatable signals.
    """
    timings_ms: list[float] = []
    sizes_kb: list[float] = []

    for _ in range(max(1, attempts)):
        start = time.perf_counter()
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
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
        # Map to fields your scorer expects (simple proxies):
        "fcp_ms": round(avg_ms, 1),
        "lcp_ms": round(avg_ms * 1.6, 1),
    }


def analyze_onpage(pages_html: Dict[str, str]) -> Tuple[Dict[str, int], Dict[str, Any]]:
    """
    Parse crawled HTML pages to compute on-page metrics (+ small details payload).
    """
    missing_title = 0
    missing_meta_desc = 0
    multiple_h1 = 0
    images_missing_alt = 0
    page_samples: list[Dict[str, Any]] = []

    for idx, (page_url, html) in enumerate(pages_html.items()):
        soup = BeautifulSoup(html, "html.parser")

        # <title>
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        if not title:
            missing_title += 1

        # <meta name="description">
        meta_desc = ""
        md = soup.find("meta", attrs={"name": "description"})
        if md and md.get("content"):
            meta_desc = md["content"].strip()
        if not meta_desc:
            missing_meta_desc += 1

        # H1 count
        h1s = soup.find_all("h1")
        if len(h1s) > 1:
            multiple_h1 += 1

        # <img alt="">
        for img in soup.find_all("img"):
            if img.has_attr("alt"):
                if not str(img.get("alt") or "").strip():
                    images_missing_alt += 1
            else:
                images_missing_alt += 1

        if idx < 8:
            page_samples.append({
                "url": page_url,
                "title": title[:120],
                "has_meta_description": bool(meta_desc),
                "h1_count": len(h1s),
            })

    onpage = {
        "missing_title_tags": missing_title,
        "missing_meta_descriptions": missing_meta_desc,
        "multiple_h1": multiple_h1,
        "images_missing_alt": images_missing_alt,
    }
    details = {"page_samples": page_samples}
    return onpage, details


def build_priorities(onpage: Dict[str, int], broken_links_total: int, perf: Dict[str, float]) -> list[str]:
    prios: list[str] = []
    if broken_links_total > 0:
        prios.append(f"Fix {broken_links_total} broken links (internal + external).")
    if onpage.get("missing_meta_descriptions", 0) > 0:
        prios.append("Add missing meta descriptions to key pages.")
    if onpage.get("missing_title_tags", 0) > 0:
        prios.append("Write meaningful <title> tags on pages where they are missing.")
    if onpage.get("multiple_h1", 0) > 0:
        prios.append("Reduce multiple <h1> headings per page to a single primary heading.")
    if onpage.get("images_missing_alt", 0) > 0:
        prios.append("Add descriptive alt text to images for accessibility & SEO.")
    if perf.get("response_ms", 0.0) > 2200:
        prios.append("Reduce server response time (cache/CDN/minify). Target < 1s.")
    if not prios:
        prios.append("Maintain current quality; consider performance budgets and structured data.")
    return prios


def build_executive_summary(grade: str, overall: float, crawl_pages: int, broken: int) -> str:
    if grade in ("A+", "A"):
        tone = "strong technical baseline"
    elif grade == "B":
        tone = "healthy foundation with clear optimization opportunities"
    elif grade == "C":
        tone = "noticeable issues impacting UX and crawlability"
    else:
        tone = "significant issues that warrant immediate attention"

    broken_txt = "no broken links detected" if broken == 0 else f"{broken} broken links found"
    return (
        f"The automated audit scanned {crawl_pages} pages and produced an overall score of "
        f"{overall:.0f} ({grade}). Results indicate {tone}. Additionally, {broken_txt}. "
        "Address the prioritized items to unlock quick wins over the next sprint."
    )


def run_audit(url: str | Any) -> Dict[str, Any]:
    """
    REAL audit flow:
      1) Normalize URL
      2) Crawl (HTML + links + broken checks)
      3) Analyze on-page metrics from actual HTML
      4) Measure simple perf proxies
      5) Score using compute_scores()
      6) Return a structured, chart-ready payload (for API/UI/PDF)
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
