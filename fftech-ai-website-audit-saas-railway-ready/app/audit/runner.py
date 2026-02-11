# -*- coding: utf-8 -*-
"""
app/audit/runner.py
Most powerful & flexible Website Audit Runner (2026-ready)

Features:
- Stable IO: same input/output as always
- Pure stdlib fallback + optional requests/bs4
- Full SSL safety (certifi)
- Rich breakdown & dynamic data for beautiful PDFs
- Integrated PDF generation (no 500 errors, no N/A-only pages)
- Super extensible scoring & metrics

Input:  await WebsiteAuditRunner().run(url, html="", progress_cb=None)
Output: dict with keys:
    audited_url, overall_score, grade, breakdown, chart_data, dynamic
"""
from __future__ import annotations
import asyncio
import os
import re
import ssl
import time
import datetime as _dt
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

ProgressCB = Optional[Callable[[str, int, Optional[dict]], Union[None, Any]]]

# ============================================================
# PDF CONFIG (does NOT affect run() output)
# ============================================================
PDF_REPORT_TITLE: str = os.getenv("PDF_REPORT_TITLE", "Website Audit Report")
PDF_BRAND_NAME: str = os.getenv("PDF_BRAND_NAME", "FF Tech")
PDF_CLIENT_NAME: str = os.getenv("PDF_CLIENT_NAME", "N/A")
PDF_LOGO_PATH: str = os.getenv("PDF_LOGO_PATH", "")  # e.g. "app/assets/logo.png"

# -------------------------------
# Helpers
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
    if score >= 90: return "A+"
    if score >= 85: return "A"
    if score >= 75: return "B+"
    if score >= 70: return "B"
    if score >= 60: return "C"
    if score >= 50: return "D"
    return "F"

async def _maybe_progress(cb: ProgressCB, status: str, percent: int, payload: Optional[dict] = None) -> None:
    if cb:
        try:
            res = cb(status, percent, payload)
            if asyncio.iscoroutine(res):
                await res
        except Exception as e:
            logger.warning(f"Progress callback failed: {e}")

def _hostname(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""

def _is_https(url: str) -> bool:
    try:
        return urlparse(url).scheme.lower() == "https"
    except Exception:
        return False

def _truncate(s: str, n: int = 240) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[:n-3] + "..."

# -------------------------------
# SSL (Railway-safe)
# -------------------------------
def _ssl_context() -> ssl.SSLContext:
    if os.getenv("AUDIT_INSECURE_SSL", "").lower() in ("1", "true", "yes"):
        return ssl._create_unverified_context()
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()

def _requests_verify_arg() -> Any:
    if os.getenv("AUDIT_INSECURE_SSL", "").lower() in ("1", "true", "yes"):
        return False
    try:
        import certifi
        return certifi.where()
    except Exception:
        return True

# -------------------------------
# Fetchers
# -------------------------------
def _fetch_with_stdlib(url: str, timeout: float, user_agent: str, max_bytes: int) -> Dict[str, Any]:
    start = time.perf_counter()
    req = Request(
        url,
        headers={"User-Agent": user_agent, "Accept": "text/html,*/*"},
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
        html = raw.decode("utf-8", errors="replace")
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
    except ImportError:
        return None
    start = time.perf_counter()
    verify_arg = _requests_verify_arg()
    r = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": user_agent, "Accept": "text/html,*/*"},
        allow_redirects=True,
        verify=verify_arg,
    )
    content = r.content or b""
    if len(content) > max_bytes:
        content = content[:max_bytes]
    html = r.text or content.decode("utf-8", errors="replace")
    load_ms = int((time.perf_counter() - start) * 1000)
    return {
        "final_url": str(r.url),
        "status_code": r.status_code,
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

# -------------------------------
# Parsing
# -------------------------------
def _try_bs4_parse(html: str) -> Optional[Any]:
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(html or "", "html.parser")
    except Exception:
        return None

def _extract_title(html: str, soup: Any = None) -> str:
    if soup:
        try:
            return _truncate((soup.title.string or "").strip(), 200)
        except:
            pass
    m = re.search(r"<title[^>]*>(.*?)</title>", html or "", flags=re.I | re.S)
    return _truncate(re.sub(r"<[^>]+>", "", m.group(1)).strip(), 200) if m else ""

def _has_meta_description(html: str, soup: Any = None) -> bool:
    if soup:
        try:
            return bool(soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)}))
        except:
            pass
    return bool(re.search(r'<meta[^>]+name=["\']description["\']', html or "", flags=re.I))

def _canonical_url(html: str, base_url: str, soup: Any = None) -> str:
    if soup:
        try:
            link = soup.find("link", rel=re.compile(r"canonical", re.I))
            if link and link.get("href"):
                return urljoin(base_url, link["href"])
        except:
            pass
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html or "", flags=re.I)
    return urljoin(base_url, m.group(1)) if m else ""

def _count_h1(html: str, soup: Any = None) -> int:
    if soup:
        try:
            return len(soup.find_all("h1"))
        except:
            pass
    return len(re.findall(r"<h1\b", html or "", flags=re.I))

def _image_alt_stats(html: str, soup: Any = None) -> Tuple[int, int]:
    if soup:
        try:
            imgs = soup.find_all("img")
            total = len(imgs)
            missing = sum(1 for im in imgs if not (im.get("alt") or "").strip())
            return total, missing
        except:
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
    if soup:
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
        except:
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
    if soup:
        try:
            scripts = len(soup.find_all("script"))
            styles = len(soup.find_all("link", rel=re.compile(r"stylesheet", re.I)))
            return {"scripts": scripts, "styles": styles}
        except:
            pass
    scripts = len(re.findall(r"<script\b", html or "", flags=re.I))
    styles = len(re.findall(r'rel\s*=\s*["\']stylesheet["\']', html or "", flags=re.I))
    return {"scripts": scripts, "styles": styles}

# ============================================================
# PDF Integration (fully safe, no impact on run() IO)
# ============================================================
def runner_result_to_audit_data(
    runner_result: Dict[str, Any],
    *,
    client_name: str = PDF_CLIENT_NAME,
    brand_name: str = PDF_BRAND_NAME,
    audit_date: Optional[str] = None,
    website_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Converts runner result to PDF-friendly format"""
    breakdown = runner_result.get("breakdown", {})
    return {
        "audited_url": runner_result.get("audited_url", "N/A"),
        "overall_score": runner_result.get("overall_score", 0),
        "grade": runner_result.get("grade", "N/A"),
        "breakdown": breakdown,
        "chart_data": runner_result.get("chart_data", []),
        "dynamic": runner_result.get("dynamic", {"cards": [], "kv": []}),
        "audit_datetime": audit_date or _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "client_name": client_name,
        "brand_name": brand_name,
        "website_name": website_name or runner_result.get("audited_url", "N/A"),
    }

def generate_pdf_from_runner_result(
    runner_result: Dict[str, Any],
    output_path: str,
    logo_path: Optional[str] = None,
    report_title: str = PDF_REPORT_TITLE,
) -> str:
    """
    Generates PDF from audit result.
    - Safe: no crash on missing deps
    - Writes real PDF bytes to disk
    - Returns output_path on success
    """
    audit_data = runner_result_to_audit_data(runner_result)

    try:
        from app.audit.pdf_report import generate_audit_pdf
        pdf_bytes = generate_audit_pdf(audit_data)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

        logger.info(f"PDF generated successfully: {output_path}")
        return output_path

    except ImportError as e:
        logger.error(f"PDF failed: missing dependencies (reportlab?) - {e}")
        raise RuntimeError("PDF generation failed: install reportlab") from e

    except Exception as e:
        logger.exception("PDF generation failed")
        raise RuntimeError(f"PDF error: {str(e)}") from e

# ============================================================
# Core Audit Runner (unchanged IO & logic, enhanced output)
# ============================================================
@dataclass
class WebsiteAuditRunner:
    timeout: float = 25.0
    max_bytes: int = 5_000_000
    user_agent: str = "FFTechAuditBot/2.0 (+https://fftech.ai)"
    
    weights: Dict[str, float] = field(default_factory=lambda: {
        "seo": 0.35,
        "performance": 0.35,
        "links": 0.15,
        "security": 0.15
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

        # Fetch
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

        # Scoring (flexible weights)
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

        # Weighted overall score
        overall = int(
            seo * self.weights["seo"] +
            perf * self.weights["performance"] +
            link_score * self.weights["links"] +
            sec * self.weights["security"]
        )
        overall = _clamp(overall)
        grade = _grade(overall)

        await _maybe_progress(progress_cb, "building_output", 85, None)

        # Rich breakdown
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
            "competitors": {"score": 0},  # placeholder - extendable
            "ai": {"score": 0},           # placeholder - extendable
        }

        # Chart-ready data
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

        # Dynamic elements for PDF/UI
        dynamic_cards = [
            {"title": "Page Title", "body": title or "No <title> found."},
            {"title": "Load Time", "body": f"{load_ms:,} ms"},
            {"title": "Page Size", "body": f"{size_bytes:,} bytes"},
        ]

        dynamic_kv = [
            {"key": "Final URL", "value": final_url},
            {"key": "Status Code", "value": status_code},
            {"key": "HTTPS", "value": "Yes" if https else "No"},
            {"key": "HSTS", "value": "Yes" if hsts else "No"},
            {"key": "Internal Links", "value": links["internal"]},
            {"key": "External Links", "value": links["external"]},
            {"key": "Total Links", "value": links["total"]},
            {"key": "Images Missing ALT", "value": imgs_missing_alt},
            {"key": "Fetcher", "value": fetcher},
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
