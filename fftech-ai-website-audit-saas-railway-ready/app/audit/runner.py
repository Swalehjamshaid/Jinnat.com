# -*- coding: utf-8 -*-
"""
app/audit/runner.py

MOST FLEXIBLE WebsiteAuditRunner
- Pure Python compatible (stdlib fallback)
- Optional use of requests/httpx + bs4 if installed
- Keeps stable IO:
    Input : await WebsiteAuditRunner().run(url, progress_cb=None)
    Output: dict with keys:
        audited_url, overall_score, grade, breakdown, chart_data, dynamic
"""

from __future__ import annotations

import asyncio
import re
import ssl
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen

# Progress callback type:
# progress_cb(status: str, percent: int, payload: dict|None) -> None|awaitable
ProgressCB = Optional[Callable[[str, int, Optional[dict]], Union[None, Any]]]


# -------------------------------
# Helpers (safe & stable)
# -------------------------------

def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, flags=re.I):
        url = "https://" + url
    return url


def _clamp(n: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(n)))


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _grade(score: int) -> str:
    score = _safe_int(score, 0)
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


async def _maybe_progress(cb: ProgressCB, status: str, percent: int, payload: Optional[dict] = None) -> None:
    if not cb:
        return
    try:
        res = cb(status, int(percent), payload)
        if asyncio.iscoroutine(res):
            await res
    except Exception:
        # Never allow callback errors to break audit
        return


def _hostname(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def _is_https(url: str) -> bool:
    try:
        return urlparse(url).scheme.lower() == "https"
    except Exception:
        return False


def _truncate(s: str, n: int = 240) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


# -------------------------------
# Fetchers (flexible)
# -------------------------------

def _fetch_with_stdlib(url: str, timeout: float, user_agent: str, max_bytes: int) -> Dict[str, Any]:
    """
    Stdlib fetcher using urllib (works everywhere on Railway).
    Returns:
      {final_url, status_code, headers, html, bytes, load_ms}
    """
    start = time.perf_counter()

    req = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )

    ctx = ssl.create_default_context()

    with urlopen(req, timeout=timeout, context=ctx) as resp:
        status = getattr(resp, "status", 200)
        final_url = resp.geturl()
        headers = dict(resp.headers.items())

        raw = resp.read(max_bytes + 1) or b""
        if len(raw) > max_bytes:
            raw = raw[:max_bytes]

        # decode best effort
        try:
            html = raw.decode("utf-8", errors="replace")
        except Exception:
            html = raw.decode(errors="replace")

    load_ms = int((time.perf_counter() - start) * 1000)
    return {
        "final_url": final_url,
        "status_code": status,
        "headers": headers,
        "html": html,
        "bytes": len(raw),
        "load_ms": load_ms,
        "fetcher": "urllib",
    }


def _optional_fetch_with_requests(url: str, timeout: float, user_agent: str, max_bytes: int) -> Optional[Dict[str, Any]]:
    """
    If requests is installed, use it. Otherwise return None.
    """
    try:
        import requests  # type: ignore
    except Exception:
        return None

    start = time.perf_counter()
    r = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,*/*"},
        allow_redirects=True,
    )

    content = r.content or b""
    if len(content) > max_bytes:
        content = content[:max_bytes]

    # requests usually guesses encoding; ensure fallback
    try:
        html = r.text
        if not html:
            html = content.decode("utf-8", errors="replace")
    except Exception:
        html = content.decode("utf-8", errors="replace")

    load_ms = int((time.perf_counter() - start) * 1000)
    return {
        "final_url": str(r.url),
        "status_code": int(r.status_code),
        "headers": dict(r.headers),
        "html": html,
        "bytes": len(content),
        "load_ms": load_ms,
        "fetcher": "requests",
    }


def _best_fetch(url: str, timeout: float, user_agent: str, max_bytes: int) -> Dict[str, Any]:
    """
    Choose best available fetcher without forcing deps.
    """
    data = _optional_fetch_with_requests(url, timeout, user_agent, max_bytes)
    if data is not None:
        return data
    return _fetch_with_stdlib(url, timeout, user_agent, max_bytes)


# -------------------------------
# Parsing (flexible)
# -------------------------------

def _try_bs4_parse(html: str) -> Optional[Any]:
    """
    If bs4 is installed, return BeautifulSoup instance, else None.
    """
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception:
        return None
    try:
        return BeautifulSoup(html or "", "html.parser")
    except Exception:
        return None


def _extract_title(html: str, soup: Any = None) -> str:
    if soup is not None:
        try:
            t = soup.title.string if soup.title else ""
            return _truncate((t or "").strip(), 200)
        except Exception:
            pass
    m = re.search(r"<title[^>]*>(.*?)</title>", html or "", flags=re.I | re.S)
    if not m:
        return ""
    title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return _truncate(title, 200)


def _has_meta_description(html: str, soup: Any = None) -> bool:
    if soup is not None:
        try:
            tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
            return bool(tag and (tag.get("content") or "").strip())
        except Exception:
            pass
    return bool(re.search(r'<meta[^>]+name=["\']description["\'][^>]*content=', html or "", flags=re.I))


def _canonical_url(html: str, base_url: str, soup: Any = None) -> str:
    if soup is not None:
        try:
            link = soup.find("link", rel=re.compile(r"canonical", re.I))
            if link and link.get("href"):
                return urljoin(base_url, link.get("href"))
        except Exception:
            pass
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html or "", flags=re.I)
    if m:
        return urljoin(base_url, m.group(1))
    return ""


def _count_h1(html: str, soup: Any = None) -> int:
    if soup is not None:
        try:
            return len(soup.find_all("h1"))
        except Exception:
            pass
    return len(re.findall(r"<h1\b", html or "", flags=re.I))


def _image_alt_stats(html: str, soup: Any = None) -> Tuple[int, int]:
    """
    Returns: (total_imgs, imgs_missing_alt)
    """
    if soup is not None:
        try:
            imgs = soup.find_all("img")
            total = len(imgs)
            missing = 0
            for im in imgs:
                alt = (im.get("alt") or "").strip()
                if not alt:
                    missing += 1
            return total, missing
        except Exception:
            pass

    imgs = re.findall(r"<img\b[^>]*>", html or "", flags=re.I)
    total = len(imgs)
    missing = 0
    for tag in imgs:
        if not re.search(r'\balt\s*=\s*["\'].*?["\']', tag, flags=re.I | re.S):
            missing += 1
    return total, missing


def _link_counts(html: str, base_url: str, soup: Any = None) -> Dict[str, int]:
    base_host = _hostname(base_url)

    def classify(href: str) -> Optional[bool]:
        href = (href or "").strip()
        if not href:
            return None
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
            return None
        full = urljoin(base_url, href)
        host = _hostname(full)
        if not host:
            return None
        return host == base_host

    internal = external = 0

    if soup is not None:
        try:
            for a in soup.find_all("a"):
                ok = classify(a.get("href"))
                if ok is None:
                    continue
                if ok:
                    internal += 1
                else:
                    external += 1
            return {"internal": internal, "external": external, "total": internal + external}
        except Exception:
            internal = external = 0

    for m in re.findall(r'href\s*=\s*["\']([^"\']+)["\']', html or "", flags=re.I):
        ok = classify(m)
        if ok is None:
            continue
        if ok:
            internal += 1
        else:
            external += 1

    return {"internal": internal, "external": external, "total": internal + external}


def _resource_counts(html: str, soup: Any = None) -> Dict[str, int]:
    """
    Rough counts of scripts/stylesheets as a "complexity" proxy.
    """
    scripts = styles = 0
    if soup is not None:
        try:
            scripts = len(soup.find_all("script"))
            styles = len(soup.find_all("link", rel=re.compile(r"stylesheet", re.I)))
            return {"scripts": scripts, "styles": styles}
        except Exception:
            pass

    scripts = len(re.findall(r"<script\b", html or "", flags=re.I))
    styles = len(re.findall(r'rel\s*=\s*["\']stylesheet["\']', html or "", flags=re.I))
    return {"scripts": scripts, "styles": styles}


# -------------------------------
# Runner (stable IO, flexible internals)
# -------------------------------

@dataclass
class WebsiteAuditRunner:
    """
    Flexible runner used by your FastAPI / WebSocket layer.

    Input:
      await WebsiteAuditRunner().run(url, progress_cb=...)

    Output (stable keys):
      audited_url, overall_score, grade, breakdown, chart_data, dynamic
    """
    timeout: float = 25.0
    max_bytes: int = 5_000_000
    user_agent: str = "FFTechAuditBot/2.0 (+/ws)"
    weights: Dict[str, float] = field(default_factory=lambda: {
        "seo": 0.35,
        "performance": 0.35,
        "links": 0.20,
        "security": 0.10
    })

    async def run(self, url: str, progress_cb: ProgressCB = None) -> Dict[str, Any]:
        audited_url = _normalize_url(url)

        # Stable failure shape (DO NOT break UI)
        def fail(message: str) -> Dict[str, Any]:
            return {
                "audited_url": audited_url or "",
                "overall_score": 0,
                "grade": "F",
                "error": message,
                "breakdown": {},
                "chart_data": [],
                "dynamic": {"cards": [], "kv": []},
            }

        if not audited_url:
            return fail("Empty URL")

        await _maybe_progress(progress_cb, "starting", 5, {"url": audited_url})

        # Fetch in thread to keep event loop free
        await _maybe_progress(progress_cb, "fetching", 15, None)
        try:
            fetch = await asyncio.to_thread(_best_fetch, audited_url, self.timeout, self.user_agent, self.max_bytes)
        except Exception as e:
            await _maybe_progress(progress_cb, "error", 100, {"error": str(e)})
            return fail(str(e))

        final_url = fetch.get("final_url") or audited_url
        status_code = _safe_int(fetch.get("status_code"), 0)
        headers = fetch.get("headers") or {}
        html = fetch.get("html") or ""
        load_ms = _safe_int(fetch.get("load_ms"), 0)
        size_bytes = _safe_int(fetch.get("bytes"), 0)
        fetcher = fetch.get("fetcher", "unknown")

        await _maybe_progress(progress_cb, "parsing", 40, None)

        soup = _try_bs4_parse(html)

        title = _extract_title(html, soup)
        meta_desc = _has_meta_description(html, soup)
        canonical = _canonical_url(html, final_url, soup)
        h1_count = _count_h1(html, soup)
        imgs_total, imgs_missing_alt = _image_alt_stats(html, soup)
        links = _link_counts(html, final_url, soup)
        resources = _resource_counts(html, soup)

        https = _is_https(final_url)
        server_header = str(headers.get("Server", "") or headers.get("server", "") or "")
        hsts = bool(headers.get("Strict-Transport-Security") or headers.get("strict-transport-security"))

        await _maybe_progress(progress_cb, "scoring", 60, None)

        # -----------------------
        # Scoring (safe & stable)
        # -----------------------

        # PERFORMANCE (time + size + complexity)
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

        # Complexity penalty
        if resources["scripts"] > 25:
            perf -= 10
        if resources["styles"] > 12:
            perf -= 6

        perf = _clamp(perf)

        # SEO
        seo = 100
        if not title:
            seo -= 35
        else:
            if len(title) < 15:
                seo -= 10
            if len(title) > 65:
                seo -= 10

        if not meta_desc:
            seo -= 25

        if not canonical:
            seo -= 5

        if h1_count == 0:
            seo -= 15
        elif h1_count > 1:
            seo -= 10

        # Image ALT as SEO signal
        if imgs_total >= 5:
            ratio_missing = (imgs_missing_alt / max(imgs_total, 1))
            if ratio_missing > 0.5:
                seo -= 10
            elif ratio_missing > 0.25:
                seo -= 6

        seo = _clamp(seo)

        # LINKS
        link_score = 100
        if links["total"] == 0:
            link_score -= 35
        else:
            if links["internal"] == 0:
                link_score -= 25
            if links["external"] > max(25, links["internal"] * 3):
                link_score -= 10
        link_score = _clamp(link_score)

        # SECURITY
        sec = 100
        if not https:
            sec -= 45
        if status_code >= 400 or status_code == 0:
            sec -= 25
        if https and not hsts:
            sec -= 5
        sec = _clamp(sec)

        # Competitors/AI placeholders (stable keys, safe defaults)
        competitors = 0
        ai = 0

        # Weighted overall (stable)
        w = self.weights
        overall = int(
            seo * float(w.get("seo", 0.35))
            + perf * float(w.get("performance", 0.35))
            + link_score * float(w.get("links", 0.20))
            + sec * float(w.get("security", 0.10))
        )
        overall = _clamp(overall)
        grade = _grade(overall)

        await _maybe_progress(progress_cb, "building_output", 85, None)

        # -----------------------
        # Output (DO NOT change keys)
        # -----------------------
        breakdown = {
            "seo": {
                "score": seo,
                "extras": {
                    "title": title,
                    "meta_description_present": meta_desc,
                    "canonical": canonical,
                    "h1_count": h1_count,
                    "images_total": imgs_total,
                    "images_missing_alt": imgs_missing_alt,
                },
            },
            "performance": {
                "score": perf,
                "extras": {
                    "load_ms": load_ms,
                    "bytes": size_bytes,
                    "scripts": resources["scripts"],
                    "styles": resources["styles"],
                    "fetcher": fetcher,
                },
            },
            "links": {
                "score": link_score,
                "internal_links_count": links["internal"],
                "external_links_count": links["external"],
                "total_links_count": links["total"],
            },
            "security": {
                "score": sec,
                "https": https,
                "hsts": hsts,
                "status_code": status_code,
                "server": _truncate(server_header, 120),
            },
            "competitors": {"score": competitors, "top_competitor_score": competitors},
            "ai": {"score": ai},
        }

        # Chart.js-compatible (stable)
        chart_data = [
            {
                "title": "Score Breakdown",
                "type": "bar",
                "data": {
                    "labels": ["SEO", "Performance", "Links", "Security"],
                    "datasets": [
                        {
                            "label": "Score",
                            "data": [seo, perf, link_score, sec],
                            "backgroundColor": ["#fbbf24", "#38bdf8", "#22c55e", "#ef4444"],
                        }
                    ],
                },
            }
        ]

        # dynamic.cards + dynamic.kv (stable)
        dynamic_cards = [
            {"title": "Page Title", "body": title or "No <title> found."},
            {"title": "Load Time", "body": f"{load_ms} ms"},
            {"title": "Page Size", "body": f"{size_bytes} bytes"},
        ]

        dynamic_kv = [
            {"key": "final_url", "value": final_url},
            {"key": "status_code", "value": status_code},
            {"key": "https", "value": https},
            {"key": "hsts", "value": hsts},
            {"key": "internal_links", "value": links["internal"]},
            {"key": "external_links", "value": links["external"]},
            {"key": "total_links", "value": links["total"]},
            {"key": "images_missing_alt", "value": imgs_missing_alt},
            {"key": "fetcher", "value": fetcher},
        ]

        result = {
            "audited_url": final_url,
            "overall_score": overall,
            "grade": grade,
            "breakdown": breakdown,
            "chart_data": chart_data,
            "dynamic": {"cards": dynamic_cards, "kv": dynamic_kv},
        }

        await _maybe_progress(progress_cb, "completed", 100, result)
        return result
