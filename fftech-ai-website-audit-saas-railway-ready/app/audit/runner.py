# -*- coding: utf-8 -*-
"""
app/audit/runner.py
MOST FLEXIBLE & POWERFUL WebsiteAuditRunner
- Pure Python compatible (stdlib fallback)
- Optional use of requests + bs4 if installed
- Stable IO:
    Input : await WebsiteAuditRunner().run(url, html="", progress_cb=None)
    Output: dict with keys:
        audited_url, overall_score, grade, breakdown, chart_data, dynamic

PDF integration (SAFE — does NOT change run() IO):
- Proper logger setup
- Safe error handling — PDF failure never crashes the audit
- Writes real PDF bytes to disk
- Optional enrichments (PSI/Lighthouse, screenshot, axe-core, robots/sitemap, schema, mobile heuristics)
- Uses certifi for SSL (fixes CERTIFICATE_VERIFY_FAILED on Railway)
"""
from __future__ import annotations
import asyncio
import os
import re
import ssl
import time
import json
import base64
import logging
import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse, urljoin, quote_plus
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

ProgressCB = Optional[Callable[[str, int, Optional[dict]], Union[None, Any]]]

# ============================================================
# PDF CONFIG (SAFE — does not affect runner output)
# ============================================================
PDF_REPORT_TITLE: str = os.getenv("PDF_REPORT_TITLE", "Website Audit Report")
PDF_BRAND_NAME: str = os.getenv("PDF_BRAND_NAME", "FF Tech")
PDF_CLIENT_NAME: str = os.getenv("PDF_CLIENT_NAME", "N/A")
PDF_LOGO_PATH: str = os.getenv("PDF_LOGO_PATH", "")  # e.g. "app/assets/logo.png"

# Feature flags (all optional; no effect on run() IO)
PDF_ENABLE_SCREENSHOT = os.getenv("PDF_ENABLE_SCREENSHOT", "1") in {"1", "true", "yes", "on"}
PDF_ENABLE_AXE = os.getenv("PDF_ENABLE_AXE", "0") in {"1", "true", "yes", "on"}
PDF_ENABLE_ROBOTS = os.getenv("PDF_ENABLE_ROBOTS", "1") in {"1", "true", "yes", "on"}
PDF_ENABLE_SCHEMA = os.getenv("PDF_ENABLE_SCHEMA", "1") in {"1", "true", "yes", "on"}
PDF_ENABLE_MOBILE_HEUR = os.getenv("PDF_ENABLE_MOBILE_HEUR", "1") in {"1", "true", "yes", "on"}
PDF_ENABLE_BENCH = os.getenv("PDF_ENABLE_BENCH", "1") in {"1", "true", "yes", "on"}

# PSI (PageSpeed Insights) – optional
PSI_API_KEY = os.getenv("PSI_API_KEY", "").strip()
PSI_STRATEGIES = [s.strip() for s in os.getenv("PSI_STRATEGIES", "mobile,desktop").split(",") if s.strip()] or ["mobile"]

# Axe-core CDN (used only if PDF_ENABLE_AXE=1 and local axe is not provided)
AXE_CDN_URL = os.getenv("AXE_CDN_URL", "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.7.2/axe.min.js")

# ============================================================
# Helpers (unchanged compatibility)
# ============================================================
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
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B"
    if score >= 60: return "C"
    if score >= 50: return "D"
    return "F"

async def _maybe_progress(cb: ProgressCB, status: str, percent: int, payload: Optional[dict] = None) -> None:
    if not cb:
        return
    try:
        res = cb(status, int(percent), payload)
        if asyncio.iscoroutine(res):
            await res
    except Exception:
        pass

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
    return s if len(s) <= n else s[:n - 1] + "…"

# ============================================================
# SSL Helper (INTERNAL ONLY)
# ============================================================
def _ssl_context() -> ssl.SSLContext:
    insecure = os.getenv("AUDIT_INSECURE_SSL", "").lower() in {"1", "true", "yes"}
    if insecure:
        return ssl._create_unverified_context()  # TEST ONLY
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()

def _requests_verify_arg() -> Any:
    insecure = os.getenv("AUDIT_INSECURE_SSL", "").lower() in {"1", "true", "yes"}
    if insecure:
        return False
    try:
        import certifi
        return certifi.where()
    except Exception:
        return True

# ============================================================
# Fetchers (flexible)
# ============================================================
def _fetch_with_stdlib(url: str, timeout: float, user_agent: str, max_bytes: int) -> Dict[str, Any]:
    start = time.perf_counter()
    req = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    ctx = _ssl_context()
    with urlopen(req, timeout=timeout, context=ctx) as resp:
        status = getattr(resp, "status", 200)
        final_url = resp.geturl()
        headers = dict(resp.headers.items())
        raw = resp.read(max_bytes + 1) or b""
        if len(raw) > max_bytes:
            raw = raw[:max_bytes]
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
    try:
        import requests
    except Exception:
        return None
    start = time.perf_counter()
    verify_arg = _requests_verify_arg()
    r = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,*/*"},
        allow_redirects=True,
        verify=verify_arg,
    )
    content = r.content or b""
    if len(content) > max_bytes:
        content = content[:max_bytes]
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
    data = _optional_fetch_with_requests(url, timeout, user_agent, max_bytes)
    if data is not None:
        return data
    return _fetch_with_stdlib(url, timeout, user_agent, max_bytes)

# ============================================================
# Parsing (flexible)
# ============================================================
def _try_bs4_parse(html: str) -> Optional[Any]:
    try:
        from bs4 import BeautifulSoup
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
    if soup is not None:
        try:
            imgs = soup.find_all("img")
            total = len(imgs)
            missing = sum(1 for im in imgs if not (im.get("alt") or "").strip())
            return total, missing
        except Exception:
            pass
    imgs = re.findall(r"<img\b[^>]*>", html or "", flags=re.I)
    total = len(imgs)
    missing = sum(1 for tag in imgs if not re.search(r'\balt\s*=\s*["\'].*?["\']', tag, flags=re.I | re.S))
    return total, missing

def _link_counts(html: str, base_url: str, soup: Any = None) -> Dict[str, int]:
    base_host = _hostname(base_url)
    def classify(href: str) -> Optional[bool]:
        href = (href or "").strip()
        if not href or href.startswith(("#", "mailto:", "javascript:")):
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
            pass
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

# ============================================================
# PDF ENRICHMENT HELPERS (SAFE — used only in PDF path)
# ============================================================
def _http_get_text(url: str, timeout: float = 20.0) -> Tuple[int, str, Dict[str, str]]:
    """Small helper to GET a URL; returns (status, text, headers)."""
    try:
        req = Request(
            url,
            headers={"User-Agent": "FFTechAuditBot/2.0", "Accept": "*/*"},
            method="GET",
        )
        ctx = _ssl_context()
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            status = getattr(resp, "status", 200)
            headers = dict(resp.headers.items())
            raw = resp.read(6_000_000) or b""
            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception:
                text = raw.decode(errors="replace")
            return int(status), text, headers
    except Exception as e:
        logger.debug(f"_http_get_text error: {e}")
        return 0, "", {}

def _fetch_robots_and_sitemap(base_url: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    robots_info: Dict[str, Any] = {"exists": False}
    sitemap_info: Dict[str, Any] = {"exists": False}
    try:
        parsed = urlparse(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        r_status, r_text, _ = _http_get_text(urljoin(origin, "/robots.txt"))
        if r_status and r_status < 400 and r_text.strip():
            robots_info["exists"] = True
            sitemaps: List[str] = []
            allows_all = True
            for line in r_text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.lower().startswith("sitemap:"):
                    s_url = line.split(":", 1)[1].strip()
                    sitemaps.append(s_url)
                if line.lower().startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    if path and path != "/":
                        # Presence of a non-empty Disallow indicates not fully open
                        allows_all = False
            robots_info["sitemaps"] = sitemaps
            robots_info["allows_all"] = allows_all

            # Light sitemap checks on the first sitemap URL
            if sitemaps:
                s_status, s_text, _ = _http_get_text(sitemaps[0])
                if s_status and s_status < 400 and s_text.strip():
                    sitemap_info["exists"] = True
                    sitemap_info["valid"] = "<urlset" in s_text.lower() or "<sitemapindex" in s_text.lower()
                    # Approx URL count (regex-based; safe)
                    cnt = len(re.findall(r"<url\b", s_text, flags=re.I))
                    if cnt == 0:
                        # Try loc in sitemapindex
                        cnt = len(re.findall(r"<loc\b", s_text, flags=re.I))
                    sitemap_info["url_count"] = cnt
                else:
                    sitemap_info["exists"] = False
        else:
            robots_info["exists"] = False
    except Exception as e:
        logger.debug(f"robots/sitemap fetch error: {e}")
    return robots_info, sitemap_info

def _parse_structured_data(html: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"detected": False, "items": [], "errors": [], "warnings": []}
    try:
        soup = _try_bs4_parse(html)
        blocks: List[str] = []
        if soup is not None:
            for sc in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
                try:
                    txt = sc.string or sc.text or ""
                    if txt.strip():
                        blocks.append(txt)
                except Exception:
                    continue
        else:
            for m in re.finditer(
                r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                html or "", flags=re.I | re.S
            ):
                blocks.append(m.group(1))
        types: List[str] = []
        for b in blocks[:5]:
            try:
                data = json.loads(b)
            except Exception:
                continue
            def collect_types(obj):
                if isinstance(obj, dict):
                    t = obj.get("@type")
                    if isinstance(t, str):
                        types.append(t)
                    elif isinstance(t, list):
                        for tt in t:
                            if isinstance(tt, str):
                                types.append(tt)
                    for v in obj.values():
                        collect_types(v)
                elif isinstance(obj, list):
                    for it in obj:
                        collect_types(it)
            collect_types(data)
        if types:
            result["detected"] = True
            result["items"] = list(dict.fromkeys(types))[:12]
    except Exception as e:
        logger.debug(f"structured data parse error: {e}")
    return result

def _mobile_heuristics(html: str) -> Dict[str, Any]:
    out = {"viewport_meta": None, "tap_targets_small": None, "font_size_issues": None, "layout_shift_risk": None, "lab_metrics": {}}
    try:
        viewport = re.search(r'<meta[^>]+name=["\']viewport["\'][^>]*content=["\']([^"\']+)["\']', html or "", flags=re.I)
        out["viewport_meta"] = bool(viewport)
        # Heuristics (extremely light):
        # tap_targets_small: count anchor tags with <= 2 characters text (proxy for tiny taps)
        small_taps = 0
        for m in re.finditer(r"<a\b[^>]*>(.*?)</a>", html or "", flags=re.I | re.S):
            text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            if text and len(text) <= 2:
                small_taps += 1
        out["tap_targets_small"] = small_taps or 0

        # font_size_issues: count inline styles with font-size < 12px
        small_fonts = len(re.findall(r'font-size\s*:\s*(\d{1,2})px', html or "", flags=re.I))
        out["font_size_issues"] = small_fonts or 0

        # layout_shift_risk: presence of images without width/height attributes
        risky_imgs = 0
        for tag in re.findall(r"<img\b[^>]*>", html or "", flags=re.I):
            has_w = re.search(r'\bwidth\s*=', tag, flags=re.I)
            has_h = re.search(r'\bheight\s*=', tag, flags=re.I)
            if not (has_w and has_h):
                risky_imgs += 1
        out["layout_shift_risk"] = risky_imgs or 0
    except Exception:
        pass
    return out

def _psi_fetch(url: str, strategy: str = "mobile") -> Optional[Dict[str, Any]]:
    if not PSI_API_KEY:
        return None
    try:
        endpoint = (
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
            f"?url={quote_plus(url)}&strategy={quote_plus(strategy)}&category=performance&key={quote_plus(PSI_API_KEY)}"
        )
        status, text, _ = _http_get_text(endpoint, timeout=45.0)
        if not status or status >= 400 or not text.strip():
            return None
        return json.loads(text)
    except Exception as e:
        logger.debug(f"PSI fetch error ({strategy}): {e}")
        return None

def _psi_to_lighthouse_block(psi_json: Dict[str, Any], strategy: str) -> Dict[str, Any]:
    """Normalize PSI JSON to the 'lighthouse' block expected by pdf_report.py"""
    lh: Dict[str, Any] = {"config": {"device": strategy, "form_factor": strategy}, "categories": {}, "metrics": {}, "opportunities": [], "diagnostics": [], "final_url": None}
    try:
        final_url = psi_json.get("lighthouseResult", {}).get("finalUrl") or psi_json.get("id")
        lh["final_url"] = final_url

        cat_perf = psi_json.get("lighthouseResult", {}).get("categories", {}).get("performance", {})
        score = cat_perf.get("score", None)
        if score is not None:
            # PSI returns 0..1; convert to 0..100
            lh["categories"]["performance"] = int(round(float(score) * 100))

        audits = psi_json.get("lighthouseResult", {}).get("audits", {}) or {}

        def ms(aid: str) -> Optional[int]:
            try:
                v = audits.get(aid, {}).get("numericValue", None)
                if v is None: return None
                iv = int(round(float(v)))
                if iv <= 0: return None
                return iv
            except Exception:
                return None

        def num(aid: str) -> Optional[float]:
            try:
                v = audits.get(aid, {}).get("numericValue", None)
                if v is None: return None
                fv = float(v)
                if fv < 0: return None
                return fv
            except Exception:
                return None

        # Key metrics
        lh["metrics"]["LCP_ms"] = ms("largest-contentful-paint")
        # INP: PSI exposes 'experimental-interaction-to-next-paint' in newer versions; fallback to TBT/TTI context
        lh["metrics"]["INP_ms"] = ms("experimental-interaction-to-next-paint") or ms("interactive")
        lh["metrics"]["CLS"] = audits.get("cumulative-layout-shift", {}).get("numericValue", None)
        lh["metrics"]["FCP_ms"] = ms("first-contentful-paint")
        lh["metrics"]["TTFB_ms"] = ms("server-response-time") or ms("time-to-first-byte")
        lh["metrics"]["SpeedIndex_ms"] = ms("speed-index")
        lh["metrics"]["TBT_ms"] = ms("total-blocking-time")

        # Opportunities
        for aid, a in audits.items():
            try:
                det = a.get("details", {})
                if det and det.get("type") == "opportunity":
                    title = a.get("title", "")
                    savings = a.get("details", {}).get("overallSavingsMs", None)
                    if title and savings:
                        iv = int(round(float(savings)))
                        if iv > 0:
                            lh["opportunities"].append({"title": title, "estimated_savings_ms": iv})
            except Exception:
                continue
        # Diagnostics (a few useful ones)
        diag_ids = ["third-party-summary", "mainthread-work-breakdown", "unsized-images", "render-blocking-resources"]
        for did in diag_ids:
            dv = audits.get(did, {})
            if dv:
                val = dv.get("displayValue") or dv.get("title")
                if val:
                    lh["diagnostics"].append({"id": did, "value": str(val)})
    except Exception as e:
        logger.debug(f"PSI parse error: {e}")
    return lh

def _psi_field_cwv(psi_json: Dict[str, Any], strategy: str) -> Dict[str, Any]:
    """Extract field data (CrUX) if available (mobile/desktop)."""
    out: Dict[str, Any] = {}
    try:
        le = psi_json.get("loadingExperience", {}) or psi_json.get("originLoadingExperience", {}) or {}
        metrics = le.get("metrics", {})
        def metric_val(key: str) -> Optional[int]:
            try:
                v = metrics.get(key, {}).get("percentile", None)
                # PSI field percentiles are often reported in ms for *_MS & CLS as 0..1*100?
                if v is None: return None
                iv = int(round(float(v)))
                if iv <= 0: return None
                return iv
            except Exception:
                return None
        # Map to our schema
        # CLS in field metrics is usually *100? Some payloads provide decimal via distributions.
        cls_field = metrics.get("CUMULATIVE_LAYOUT_SHIFT_SCORE", {}).get("percentile")
        try:
            cls_val = None
            if cls_field is not None:
                # CLS percentile may arrive *100 in latest PSI; normalize
                fv = float(cls_field)
                cls_val = fv / 100.0 if fv > 1 else fv
        except Exception:
            cls_val = None

        out = {
            "LCP_ms": metric_val("LARGEST_CONTENTFUL_PAINT_MS"),
            "INP_ms": metric_val("INTERACTION_TO_NEXT_PAINT") or metric_val("EXPERIMENTAL_INTERACTION_TO_NEXT_PAINT_MS"),
            "TTFB_ms": metric_val("EXPERIMENTAL_TIME_TO_FIRST_BYTE_MS") or metric_val("TIME_TO_FIRST_BYTE_MS"),
            "CLS": cls_val
        }
    except Exception as e:
        logger.debug(f"PSI field data parse error: {e}")
    return {"mobile" if strategy == "mobile" else "desktop": out}

def _playwright_screenshot_b64(url: str, viewport: Tuple[int, int] = (1366, 768), full_page: bool = False) -> Optional[str]:
    if not PDF_ENABLE_SCREENSHOT:
        return None
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        logger.debug(f"Playwright not available: {e}")
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"], headless=True)
            ctx = browser.new_context(
                viewport={"width": viewport[0], "height": viewport[1]},
                device_scale_factor=1
            )
            page = ctx.new_page()
            page.set_default_navigation_timeout(30000)
            page.set_default_timeout(30000)
            page.goto(url, wait_until="networkidle")
            # Small delay to allow late async paint
            page.wait_for_timeout(800)
            buf = page.screenshot(full_page=full_page, type="png")
            b64 = base64.b64encode(buf).decode("ascii")
            ctx.close()
            browser.close()
            return b64
    except Exception as e:
        logger.debug(f"screenshot failed: {e}")
        return None

def _axe_core_scan(url: str) -> Optional[Dict[str, Any]]:
    """Run axe-core via Playwright; returns counts & top issues. Optional."""
    if not PDF_ENABLE_AXE:
        return None
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        logger.debug(f"Playwright not available for axe: {e}")
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"], headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()
            page.set_default_navigation_timeout(30000)
            page.set_default_timeout(30000)
            page.goto(url, wait_until="networkidle")
            # Inject axe-core
            page.add_script_tag(url=AXE_CDN_URL)
            # Give a moment for axe to load
            page.wait_for_timeout(500)
            result = page.evaluate("""async () => {
                if (!window.axe) { return null; }
                const res = await window.axe.run();
                return {
                    violations: res.violations.map(v => ({
                        id: v.id,
                        impact: v.impact,
                        nodes: v.nodes.length,
                        tags: v.tags || [],
                        help: v.help,
                        helpUrl: v.helpUrl
                    })),
                    passes: (res.passes || []).length
                };
            }""")
            ctx.close()
            browser.close()
            if not result:
                return None
            counts = {
                "violations": len(result.get("violations", [])),
                "passes": int(result.get("passes", 0))
            }
            buckets: Dict[str, int] = {"color-contrast": 0, "aria": 0, "keyboard": 0, "landmarks": 0, "forms": 0}
            top_issues = []
            for v in result.get("violations", [])[:10]:
                vid = v.get("id", "")
                if vid in buckets:
                    buckets[vid] = buckets.get(vid, 0) + int(v.get("nodes", 0))
                # Collect a tiny example summary
                top_issues.append({"id": vid, "nodes": str(v.get("nodes", 0)), "examples": [v.get("help","")]})
            return {
                "axe": {
                    "counts": counts,
                    "by_wcag_level": {},  # axe JSON can be expanded to map WCAG 2.2 AA explicitly if needed
                    "buckets": buckets,
                    "top_issues": top_issues
                }
            }
    except Exception as e:
        logger.debug(f"axe-core scan failed: {e}")
        return None

def _static_benchmarks() -> Dict[str, Any]:
    """Optional, static industry baseline — can be replaced by real dataset later."""
    if not PDF_ENABLE_BENCH:
        return {}
    return {
        "industry": os.getenv("PDF_BENCHMARK_INDUSTRY", "General"),
        "avg": {
            "Performance": 74,        # category score /100
            "LCP_ms": 2800,
            "INP_ms": 300,
            "CLS": 0.12,
            "Top10_Performance": 90,
            "SEO": 78,
            "Top10_SEO": 90,
            "Security": 72,
            "Top10_Security": 88,
            "Accessibility": 70,
            "Top10_Accessibility": 88
        }
    }

# ============================================================
# PDF HELPERS (SAFE — does not affect run() output)
# ============================================================
def runner_result_to_audit_data(
    runner_result: Dict[str, Any],
    *,
    client_name: str = PDF_CLIENT_NAME,
    brand_name: str = PDF_BRAND_NAME,
    audit_date: Optional[str] = None,
    website_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Converts runner result to base format expected by pdf_report.py (no external calls)."""
    breakdown = runner_result.get("breakdown", {})
    dynamic = runner_result.get("dynamic", {"cards": [], "kv": []})

    return {
        "audited_url": runner_result.get("audited_url", "N/A"),
        "overall_score": runner_result.get("overall_score", 0),
        "grade": runner_result.get("grade", "N/A"),
        "audit_datetime": audit_date or _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "brand_name": brand_name,
        "client_name": client_name,
        "website_name": website_name or runner_result.get("audited_url", "N/A"),
        "scores": {
            "overall": runner_result.get("overall_score", 0),
            "performance": breakdown.get("performance", {}).get("score", 0),
            "seo": breakdown.get("seo", {}).get("score", 0),
            "security": breakdown.get("security", {}).get("score", 0),
            "links": breakdown.get("links", {}).get("score", 0),
            # accessibility / ux intentionally omitted (runner doesn't compute them)
        },
        "breakdown": breakdown,
        "chart_data": runner_result.get("chart_data", []),
        "dynamic": dynamic,
        # Small, business-facing summary
        "summary": {
            "risk_level": "Low" if runner_result.get("overall_score", 0) >= 80 else ("Medium" if runner_result.get("overall_score", 0) >= 60 else "High"),
            "traffic_impact": "High impact issues detected" if runner_result.get("overall_score", 0) < 70 else "Good performance detected"
        },
        "priority_actions": [
            "Optimize page load time and reduce image sizes",
            "Add/improve meta description and canonical tags",
            "Enable HSTS and review security headers",
        ]
    }

def _enrich_audit_data_for_pdf(audit_data: Dict[str, Any], runner_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adds optional, best-effort enrichments needed by the PDF without changing run() IO.
    All network/dep failures are swallowed safely.
    """
    url = audit_data.get("audited_url") or runner_result.get("audited_url") or ""
    html = ""
    try:
        # We might have HTML in runner_result dynamic kv; else skip
        html = ""  # (not stored by runner currently)
    except Exception:
        html = ""

    # Benchmarks (static stub)
    try:
        bench = _static_benchmarks()
        if bench:
            audit_data["benchmarks"] = bench
    except Exception:
        pass

    # PSI (per strategy)
    field_cwv: Dict[str, Any] = {}
    lhr_merged: Dict[str, Any] = {"config": {}, "categories": {}, "metrics": {}, "opportunities": [], "diagnostics": []}
    try:
        for strat in PSI_STRATEGIES:
            psi = _psi_fetch(url, strat)
            if not psi:
                continue
            block = _psi_to_lighthouse_block(psi, strat)
            # Merge: prefer mobile for metrics if present; keep opportunities/diagnostics union
            # Final URL & categories from first result
            if not lhr_merged.get("final_url") and block.get("final_url"):
                lhr_merged["final_url"] = block["final_url"]
            lhr_merged["config"] = {"device": strat, "form_factor": strat}
            for k, v in (block.get("categories") or {}).items():
                lhr_merged.setdefault("categories", {})
                if v is not None:
                    lhr_merged["categories"][k] = v
            for k, v in (block.get("metrics") or {}).items():
                if v is not None:
                    lhr_merged["metrics"][k] = v
            for op in block.get("opportunities", []):
                if op not in lhr_merged["opportunities"]:
                    lhr_merged["opportunities"].append(op)
            for dg in block.get("diagnostics", []):
                if dg not in lhr_merged["diagnostics"]:
                    lhr_merged["diagnostics"].append(dg)
            # Field CWV if available for that strategy
            fld = _psi_field_cwv(psi, strat)
            field_cwv.update(fld or {})
        if lhr_merged.get("metrics"):
            audit_data["lighthouse"] = lhr_merged
        if field_cwv:
            audit_data["field_cwv"] = field_cwv
    except Exception as e:
        logger.debug(f"PSI enrichment failed: {e}")

    # Robots + Sitemap
    if PDF_ENABLE_ROBOTS:
        try:
            robots, sitemap = _fetch_robots_and_sitemap(url)
            if robots:
                audit_data["robots"] = robots
            if sitemap:
                audit_data["sitemap"] = sitemap
        except Exception as e:
            logger.debug(f"robots/sitemap enrichment failed: {e}")

    # Structured Data (HTML needed; if missing, do a light GET)
    if PDF_ENABLE_SCHEMA:
        try:
            if not html:
                status, html_text, _ = _http_get_text(url)
                if status and status < 400:
                    html = html_text
            if html:
                audit_data["structured_data"] = _parse_structured_data(html)
        except Exception as e:
            logger.debug(f"structured data enrichment failed: {e}")

    # Mobile heuristics
    if PDF_ENABLE_MOBILE_HEUR:
        try:
            if not html:
                status, html_text, _ = _http_get_text(url)
                if status and status < 400:
                    html = html_text
            if html:
                audit_data["mobile"] = _mobile_heuristics(html)
        except Exception as e:
            logger.debug(f"mobile heuristics enrichment failed: {e}")

    # Screenshot (homepage)
    try:
        b64 = _playwright_screenshot_b64(url, viewport=(1366, 768), full_page=False)
        if b64:
            audit_data.setdefault("assets", {})
            audit_data["assets"]["homepage_screenshot_b64"] = b64
    except Exception as e:
        logger.debug(f"screenshot enrichment failed: {e}")

    # Accessibility via axe-core (optional)
    try:
        axe_block = _axe_core_scan(url)
        if axe_block:
            audit_data.setdefault("accessibility", {})
            audit_data["accessibility"].update(axe_block)
    except Exception as e:
        logger.debug(f"axe-core enrichment failed: {e}")

    # Competitors stub (optional manual fill later)
    try:
        comp = os.getenv("PDF_COMPETITORS_JSON", "").strip()
        if comp:
            audit_data["competitors"] = json.loads(comp)
    except Exception:
        pass

    # Append minimal history if available via env
    try:
        hist = os.getenv("PDF_HISTORY_JSON", "").strip()
        if hist:
            audit_data["history"] = json.loads(hist)
    except Exception:
        pass

    return audit_data

def generate_pdf_from_runner_result(
    runner_result: Dict[str, Any],
    output_path: str,
    logo_path: Optional[str] = None,
    report_title: str = PDF_REPORT_TITLE,
) -> str:
    """
    SAFE PDF generation helper — does not affect run() output.
    Uses positional arguments only to avoid keyword errors.
    Writes PDF bytes to disk and returns the path.
    """
    audit_data = runner_result_to_audit_data(runner_result)
    # Optional enrichments that do NOT modify the runner IO contract
    try:
        audit_data = _enrich_audit_data_for_pdf(audit_data, runner_result)
    except Exception as e:
        logger.debug(f"PDF enrichment skipped due to error: {e}")

    try:
        from app.audit.pdf_report import generate_audit_pdf
        pdf_bytes = generate_audit_pdf(audit_data)

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

        logger.info(f"PDF generated successfully: {output_path}")
        return output_path

    except ImportError as e:
        logger.error(f"PDF generation failed: missing dependencies (reportlab?) - {e}")
        raise RuntimeError("PDF dependencies missing. Install reportlab and Pillow.") from e

    except Exception as e:
        logger.exception("PDF generation error")
        raise RuntimeError(f"PDF generation failed: {str(e)}") from e

# ============================================================
# Runner Core (unchanged IO)
# ============================================================
@dataclass
class WebsiteAuditRunner:
    timeout: float = 25.0
    max_bytes: int = 5_000_000
    user_agent: str = "FFTechAuditBot/2.0 (+/ws)"
    weights: Dict[str, float] = field(default_factory=lambda: {
        "seo": 0.35,
        "performance": 0.35,
        "links": 0.20,
        "security": 0.10
    })

    async def run(self, url: str, html: str = "", progress_cb: ProgressCB = None) -> Dict[str, Any]:
        audited_url = _normalize_url(url)

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

        if html.strip():
            fetch = {
                "final_url": audited_url,
                "status_code": 200,
                "headers": {},
                "html": html,
                "bytes": len(html.encode()),
                "load_ms": 0,
                "fetcher": "pre-fetched",
            }
            await _maybe_progress(progress_cb, "fetched", 15, {"fetcher": "pre-fetched"})
        else:
            await _maybe_progress(progress_cb, "fetching", 15, None)
            try:
                fetch = await asyncio.to_thread(_best_fetch, audited_url, self.timeout, self.user_agent, self.max_bytes)
            except Exception as e:
                await _maybe_progress(progress_cb, "error", 100, {"error": str(e)})
                return fail(str(e))

        final_url = fetch.get("final_url") or audited_url
        status_code = _safe_int(fetch.get("status_code"), 0)
        headers = fetch.get("headers") or {}
        html_content = fetch.get("html") or ""
        load_ms = _safe_int(fetch.get("load_ms"), 0)
        size_bytes = _safe_int(fetch.get("bytes"), 0)
        fetcher = fetch.get("fetcher", "unknown")

        await _maybe_progress(progress_cb, "parsing", 40, None)
        soup = _try_bs4_parse(html_content)

        title = _extract_title(html_content, soup)
        meta_desc = _has_meta_description(html_content, soup)
        canonical = _canonical_url(html_content, final_url, soup)
        h1_count = _count_h1(html_content, soup)
        imgs_total, imgs_missing_alt = _image_alt_stats(html_content, soup)
        links = _link_counts(html_content, final_url, soup)
        resources = _resource_counts(html_content, soup)
        https = _is_https(final_url)
        server_header = str(headers.get("Server", "") or headers.get("server", "") or "")
        hsts = bool(headers.get("Strict-Transport-Security") or headers.get("strict-transport-security"))

        await _maybe_progress(progress_cb, "scoring", 60, None)

        perf = 100
        if load_ms > 8000: perf -= 45
        elif load_ms > 5000: perf -= 35
        elif load_ms > 3000: perf -= 25
        elif load_ms > 1500: perf -= 15
        elif load_ms > 800: perf -= 8
        if size_bytes > 3_000_000: perf -= 25
        elif size_bytes > 1_500_000: perf -= 15
        elif size_bytes > 800_000: perf -= 8
        if resources["scripts"] > 25: perf -= 10
        if resources["styles"] > 12: perf -= 6
        perf = _clamp(perf)

        seo = 100
        if not title: seo -= 35
        else:
            if len(title) < 15: seo -= 10
            if len(title) > 65: seo -= 10
        if not meta_desc: seo -= 25
        if not canonical: seo -= 5
        if h1_count == 0: seo -= 15
        elif h1_count > 1: seo -= 10
        if imgs_total >= 5:
            ratio_missing = imgs_missing_alt / max(imgs_total, 1)
            if ratio_missing > 0.5: seo -= 10
            elif ratio_missing > 0.25: seo -= 6
        seo = _clamp(seo)

        link_score = 100
        if links["total"] == 0: link_score -= 35
        else:
            if links["internal"] == 0: link_score -= 25
            if links["external"] > max(25, links["internal"] * 3): link_score -= 10
        link_score = _clamp(link_score)

        sec = 100
        if not https: sec -= 45
        if status_code >= 400 or status_code == 0: sec -= 25
        if https and not hsts: sec -= 5
        sec = _clamp(sec)

        competitors = 0
        ai = 0

        w = self.weights
        overall = int(
            seo * w["seo"] +
            perf * w["performance"] +
            link_score * w["links"] +
            sec * w["security"]
        )
        overall = _clamp(overall)
        grade = _grade(overall)

        await _maybe_progress(progress_cb, "building_output", 85, None)

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

        chart_data = [
            {
                "title": "Score Breakdown",
                "type": "bar",
                "data": {
                    "labels": ["SEO", "Performance", "Links", "Security"],
                    "datasets": [{
                        "label": "Score",
                        "data": [seo, perf, link_score, sec],
                        "backgroundColor": ["#fbbf24", "#38bdf8", "#22c55e", "#ef4444"],
                    }]
                }
            }
        ]

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
