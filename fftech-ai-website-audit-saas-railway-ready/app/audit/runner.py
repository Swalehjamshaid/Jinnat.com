# -*- coding: utf-8 -*-
"""
Website Audit Runner
- This file must be Python only (NO HTML).
- Used by: from app.audit.runner import WebsiteAuditRunner
"""

from __future__ import annotations

import asyncio
import re
import ssl
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Union
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen

# Type for progress callback:
# progress(status: str, percent: int, payload: dict|None) -> None|awaitable
ProgressCB = Optional[Callable[[str, int, Optional[dict]], Union[None, Any]]]


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, flags=re.I):
        url = "https://" + url
    return url


def _grade(score: int) -> str:
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _clamp(n: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, n))


def _simple_extract_links(html: str, base_url: str) -> Dict[str, int]:
    # Very lightweight link extraction (no external deps)
    # Counts internal/external links based on hostname.
    links = re.findall(r'href\s*=\s*["\']([^"\']+)["\']', html, flags=re.I)
    base_host = urlparse(base_url).netloc.lower()
    internal = 0
    external = 0

    for href in links:
        href = href.strip()
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
            continue

        full = urljoin(base_url, href)
        host = urlparse(full).netloc.lower()

        if not host:
            continue
        if host == base_host:
            internal += 1
        else:
            external += 1

    return {"internal": internal, "external": external, "total": internal + external}


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    if not m:
        return ""
    # Strip tags and whitespace
    title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return title[:200]


def _has_meta_description(html: str) -> bool:
    return bool(re.search(r'<meta[^>]+name=["\']description["\'][^>]*>', html, flags=re.I))


def _count_h1(html: str) -> int:
    return len(re.findall(r"<h1\b", html, flags=re.I))


def _is_https(url: str) -> bool:
    return urlparse(url).scheme.lower() == "https"


def _fetch_html(url: str, timeout: float = 25.0) -> Dict[str, Any]:
    # Uses urllib only (works on minimal containers)
    # Returns: {status_code, final_url, load_ms, html, bytes}
    start = time.perf_counter()

    req = Request(
        url,
        headers={
            "User-Agent": "FFTechAuditBot/1.0 (+https://example.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )

    # Create SSL context (avoid common SSL issues)
    ctx = ssl.create_default_context()

    with urlopen(req, timeout=timeout, context=ctx) as resp:
        status = getattr(resp, "status", 200)
        final_url = resp.geturl()
        raw = resp.read() or b""
        html = ""
        try:
            html = raw.decode("utf-8", errors="replace")
        except Exception:
            html = raw.decode(errors="replace")

    load_ms = int((time.perf_counter() - start) * 1000)
    return {
        "status_code": status,
        "final_url": final_url,
        "load_ms": load_ms,
        "html": html,
        "bytes": len(raw),
    }


async def _maybe_call_progress(cb: ProgressCB, status: str, percent: int, payload: Optional[dict] = None) -> None:
    if not cb:
        return
    try:
        res = cb(status, int(percent), payload)
        if asyncio.iscoroutine(res):
            await res
    except Exception:
        # Never allow progress callback to break the audit
        return


@dataclass
class WebsiteAuditRunner:
    """
    Stable runner used by the FastAPI/WebSocket layer.

    You can call:
      runner = WebsiteAuditRunner()
      result = await runner.run(url, progress_cb=...)

    Output keys are intentionally stable:
      audited_url, overall_score, grade, breakdown, chart_data, dynamic
    """

    timeout: float = 25.0

    async def run(self, url: str, progress_cb: ProgressCB = None) -> Dict[str, Any]:
        audited_url = _normalize_url(url)
        if not audited_url:
            return {
                "audited_url": "",
                "overall_score": 0,
                "grade": "F",
                "error": "Empty URL",
                "breakdown": {},
                "chart_data": [],
                "dynamic": {"cards": [], "kv": []},
            }

        await _maybe_call_progress(progress_cb, "starting", 5, {"url": audited_url})

        # Fetch (in thread to avoid blocking event loop)
        await _maybe_call_progress(progress_cb, "fetching", 15, None)
        try:
            fetch = await asyncio.to_thread(_fetch_html, audited_url, self.timeout)
        except Exception as e:
            await _maybe_call_progress(progress_cb, "error", 100, {"error": str(e)})
            return {
                "audited_url": audited_url,
                "overall_score": 0,
                "grade": "F",
                "error": str(e),
                "breakdown": {},
                "chart_data": [],
                "dynamic": {"cards": [], "kv": []},
            }

        final_url = fetch.get("final_url") or audited_url
        html = fetch.get("html") or ""
        status_code = _safe_int(fetch.get("status_code"), 0)
        load_ms = _safe_int(fetch.get("load_ms"), 0)
        size_bytes = _safe_int(fetch.get("bytes"), 0)

        await _maybe_call_progress(progress_cb, "analyzing", 45, None)

        # Basic extractions
        title = _extract_title(html)
        meta_desc = _has_meta_description(html)
        h1_count = _count_h1(html)
        link_counts = _simple_extract_links(html, final_url)
        https = _is_https(final_url)

        # ---- Scoring (simple but stable) ----
        # Performance score: based on load_ms and size
        perf = 100
        if load_ms > 8000:
            perf -= 45
        elif load_ms > 5000:
            perf -= 35
        elif load_ms > 3000:
            perf -= 25
        elif load_ms > 1500:
            perf -= 15
        elif load_ms > 800:
            perf -= 8

        if size_bytes > 3_000_000:
            perf -= 25
        elif size_bytes > 1_500_000:
            perf -= 15
        elif size_bytes > 800_000:
            perf -= 8

        perf = _clamp(perf)

        # SEO score: title, meta description, H1 sanity
        seo = 100
        if not title:
            seo -= 35
        elif len(title) < 15:
            seo -= 10
        elif len(title) > 65:
            seo -= 10

        if not meta_desc:
            seo -= 25

        # H1 rules: ideally 1
        if h1_count == 0:
            seo -= 15
        elif h1_count > 1:
            seo -= 10

        seo = _clamp(seo)

        # Links score: internal linking helps; too many externals can hurt slightly
        links = 100
        if link_counts["total"] == 0:
            links -= 35
        else:
            if link_counts["internal"] == 0:
                links -= 25
            if link_counts["external"] > max(20, link_counts["internal"] * 3):
                links -= 10
        links = _clamp(links)

        # Security score: https, status code sanity
        security = 100
        if not https:
            security -= 45
        if status_code >= 400 or status_code == 0:
            security -= 25
        security = _clamp(security)

        # Competitors / AI: placeholders but stable keys (do not break UI)
        competitors = 0
        ai = 0

        breakdown = {
            "seo": {"score": seo},
            "performance": {"score": perf, "extras": {"load_ms": load_ms, "bytes": size_bytes}},
            "links": {
                "score": links,
                "internal_links_count": link_counts["internal"],
                "external_links_count": link_counts["external"],
                "total_links_count": link_counts["total"],
            },
            "security": {"score": security, "https": https, "status_code": status_code},
            "competitors": {"score": competitors, "top_competitor_score": competitors},
            "ai": {"score": ai},
        }

        # Weighted overall
        overall = _clamp(int((seo * 0.35) + (perf * 0.35) + (links * 0.20) + (security * 0.10)))
        grade = _grade(overall)

        await _maybe_call_progress(progress_cb, "building_output", 80, None)

        # Chart.js ready data (stable)
        chart_data = [
            {
                "title": "Score Breakdown",
                "type": "bar",
                "data": {
                    "labels": ["SEO", "Performance", "Links", "Security"],
                    "datasets": [
                        {
                            "label": "Score",
                            "data": [seo, perf, links, security],
                            "backgroundColor": ["#fbbf24", "#38bdf8", "#22c55e", "#ef4444"],
                        }
                    ],
                },
            }
        ]

        # Dynamic cards (stable)
        dynamic_cards = [
            {"title": "Page Title", "body": title or "No <title> found."},
            {"title": "Load Time", "body": f"{load_ms} ms"},
            {"title": "Page Size", "body": f"{size_bytes} bytes"},
        ]

        # Key-value inspector (stable)
        dynamic_kv = [
            {"key": "final_url", "value": final_url},
            {"key": "status_code", "value": status_code},
            {"key": "https", "value": https},
            {"key": "meta_description_present", "value": meta_desc},
            {"key": "h1_count", "value": h1_count},
            {"key": "internal_links", "value": link_counts["internal"]},
            {"key": "external_links", "value": link_counts["external"]},
        ]

        result = {
            "audited_url": final_url,
            "overall_score": overall,
            "grade": grade,
            "breakdown": breakdown,
            "chart_data": chart_data,
            "dynamic": {"cards": dynamic_cards, "kv": dynamic_kv},
        }

        await _maybe_call_progress(progress_cb, "completed", 100, result)
        return result
``
