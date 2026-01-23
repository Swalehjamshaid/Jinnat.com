v
# app/audit/grader.py
"""
International‑quality, API‑independent website grading.
- No external services (PSI/Gemini) are used.
- Estimates performance metrics from HTTP timings + HTML structure.
- Computes category scores (performance, UX, connectivity, security) for UI radar chart.
- Returns a stable, JSON-serializable report with backward-compatible keys.

Public keys preserved:
  - url, metadata.timestamp, metadata.duration
  - connectivity: {status, detail, error_code}
  - performance: {overall_score (0..1), fcp, lcp, cls}  # estimated display strings
  - score: float 0..100
  - ai_summary: string

New keys for UI:
  - category_scores: {performance, ux, connectivity, security} (0..100)
  - health_index: int (rounded score)
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import certifi
import httpx
from time import perf_counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Dict, Any, Optional, Tuple, List

from pydantic import BaseModel, ConfigDict, Field

# Offline AI summary (no external API)
from app.services.ai_service import AIService

logger = logging.getLogger("AuditEngine")


# ------------------------------
# Data Models
# ------------------------------
class AuditMetrics(BaseModel):
    overall_score: float = Field(..., ge=0, le=1)
    fcp: str
    lcp: str
    cls: str
    model_config = ConfigDict(from_attributes=True)


# ------------------------------
# Internal utilities
# ------------------------------
class _TagCounter(HTMLParser):
    """Count tags for basic complexity signals."""
    def __init__(self) -> None:
        super().__init__()
        self.scripts = 0
        self.images = 0
        self.stylesheets = 0
        self.dom_nodes = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        self.dom_nodes += 1
        if tag == "script":
            self.scripts += 1
        elif tag == "img":
            self.images += 1
        elif tag == "link":
            try:
                rel = next((v for k, v in attrs if k == "rel"), "")
                as_attr = next((v for k, v in attrs if k == "as"), "")
                href = next((v for k, v in attrs if k == "href"), "")
                if "stylesheet" in str(rel).lower() or (href and as_attr == "style"):
                    self.stylesheets += 1
            except Exception:
                pass


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _score_linear(value: float, good: float, bad: float, higher_is_better: bool = False) -> float:
    """
    Convert a metric value to 0..1 score based on linear interpolation.
    - If higher_is_better=False: good < bad (lower is better)
    - If higher_is_better=True:  good > bad  (higher is better)
    """
    if good == bad:
        return 1.0
    v, g, b = value, good, bad
    if higher_is_better:
        # Normalize to lower-is-better by flipping magnitudes
        v, g, b = -v, -g, -b
    t = (v - g) / (b - g)
    return _clamp(1.0 - t, 0.0, 1.0)


def _format_seconds_est(seconds: Optional[float]) -> str:
    return "N/A" if seconds is None else f"{seconds:.2f} s (est.)"


async def _fetch_with_timings(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_bytes: int = 1_048_576,  # read up to 1 MiB
) -> Tuple[int, float, float, bytes, str, Dict[str, str]]:
    """
    Stream the URL to measure:
      - TTFB (s): time to first response chunk
      - total_time (s): time to read stream (or until max_bytes)
      - status_code
      - content (partial up to max_bytes)
      - final_url (after redirects)
      - headers (response headers)
    """
    t_start = perf_counter()
    status_code = 0
    ttfb_s: Optional[float] = None
    total_bytes = 0
    content_chunks: List[bytes] = []
    final_url = url
    headers: Dict[str, str] = {}

    async with client.stream("GET", url, follow_redirects=True) as resp:
        status_code = resp.status_code
        final_url = str(resp.url)
        headers = {k: v for k, v in resp.headers.items()}
        async for chunk in resp.aiter_bytes():
            if ttfb_s is None:
                ttfb_s = perf_counter() - t_start
            if not chunk:
                break
            content_chunks.append(chunk)
            total_bytes += len(chunk)
            if total_bytes >= max_bytes:
                break
        total_time = perf_counter() - t_start

    return status_code, (ttfb_s or total_time), total_time, b"".join(content_chunks), final_url, headers


def _estimate_fcp_lcp(
    ttfb_s: float,
    total_time_s: float,
    html_kb: float,
    scripts: int,
    stylesheets: int,
    images: int,
) -> Tuple[float, float]:
    """
    Heuristic FCP/LCP without a real browser:
      FCP ≈ TTFB + parsing penalty (html size + blocking assets)
      LCP ≈ max(FCP, total_time) + small image penalty
    """
    parse_penalty = 0.0015 * html_kb + 0.04 * scripts + 0.02 * stylesheets
    fcp = ttfb_s + parse_penalty
    image_penalty = 0.03 * min(images, 30)
    lcp = max(fcp, total_time_s) + image_penalty
    fcp = _clamp(fcp, 0.05, 30.0)
    lcp = _clamp(lcp, fcp, 60.0)
    return fcp, lcp


def _estimate_overall_score(
    ttfb_s: float,
    total_time_s: float,
    html_kb: float,
    scripts: int,
    stylesheets: int,
    status_code: int,
) -> float:
    """
    Blend subscores into 0..1:
      - TTFB      (0.25): 0.2s → 1.0, 2.0s → 0.0
      - Total     (0.35): 2.0s → 1.0, 10s  → 0.0
      - Size      (0.20): 150KB → 1.0, 2000KB → 0.0
      - Scripts   (0.10):   5   → 1.0,   40    → 0.0
      - CSS       (0.10):   3   → 1.0,   20    → 0.0
    Non-2xx/3xx: heavy penalty.
    """
    w_ttfb, w_total, w_size, w_scripts, w_css = 0.25, 0.35, 0.20, 0.10, 0.10
    s_ttfb = _score_linear(ttfb_s, good=0.2, bad=2.0)
    s_total = _score_linear(total_time_s, good=2.0, bad=10.0)
    s_size = _score_linear(html_kb, good=150.0, bad=2000.0)
    s_scripts = _score_linear(float(scripts), good=5.0, bad=40.0)
    s_css = _score_linear(float(stylesheets), good=3.0, bad=20.0)

    base = (
        w_ttfb * s_ttfb
        + w_total * s_total
        + w_size * s_size
        + w_scripts * s_scripts
        + w_css * s_css
    )

    if not (200 <= status_code < 400):
        base *= 0.2

    return _clamp(base, 0.0, 1.0)


def _analyze_html(content: bytes) -> Tuple[float, int, int, int, int]:
    """
    Analyze up to 1 MiB of HTML and return:
      (html_kb, scripts, stylesheets, images, dom_nodes)
    """
    try:
        text = content.decode("utf-8", errors="ignore")
    except Exception:
        text = ""

    parser = _TagCounter()
    try:
        parser.feed(text)
    except Exception:
        pass

    html_kb = len(content) / 1024.0
    return html_kb, parser.scripts, parser.stylesheets, parser.images, parser.dom_nodes


def _security_score_from_headers(
    status: str,
    headers: Dict[str, str],
    final_url: str,
) -> float:
    """
    Compute a 0..1 security score using response headers + connectivity status.
    Heuristics:
      - HTTPS success: strong baseline; SSL_BYPASSED reduces score.
      - Bonus for HSTS, CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy.
    """
    scheme_is_https = final_url.lower().startswith("https://")
    # Base from connectivity
    base = 1.0 if status == "SUCCESS" else (0.7 if status == "WARNING" else 0.2)
    if not scheme_is_https:
        base *= 0.6

    h = {k.lower(): v for k, v in headers.items()}
    points = 0.0
    if "strict-transport-security" in h:
        points += 0.15
    if "content-security-policy" in h:
        points += 0.2
    if h.get("x-content-type-options", "").lower() == "nosniff":
        points += 0.1
    if "x-frame-options" in h:
        points += 0.1
    if "referrer-policy" in h:
        points += 0.05

    score = _clamp(base + points, 0.0, 1.0)
    return score


# ------------------------------
# Public Grader
# ------------------------------
class WebsiteGrader:
    """
    Pure‑Python grader:
      - validate_connectivity(): reachability with secure/insecure fallback
      - fetch_performance(): estimates based on timings & HTML complexity
      - run_full_audit(): orchestrates, adds category scores, and returns report
    """

    def __init__(self) -> None:
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.ai_service = AIService()  # Offline summarizer
        # Tunables
        self.connect_timeout = 15.0
        self.fetch_timeout = 45.0
        self.max_html_bytes = 1_048_576  # 1 MiB

    async def validate_connectivity(self, url: str) -> Dict[str, Any]:
        """
        Try HTTPS first; on httpx HTTPError fall back to verify=False and mark WARNING.
        """
        try:
            async with httpx.AsyncClient(
                verify=self.ssl_context,
                timeout=self.connect_timeout,
                http2=True,
                follow_redirects=True,
                headers={"User-Agent": "FFTechAudit/1.0"}
            ) as client:
                await client.get(url)
                return {"status": "SUCCESS", "detail": "Secure", "error_code": None}
        except (httpx.ConnectTimeout, httpx.ReadTimeout):
            return {"status": "FAILURE", "detail": "TIMEOUT", "error_code": "NET_TIMEOUT"}
        except httpx.HTTPError:
            try:
                async with httpx.AsyncClient(
                    verify=False,
                    timeout=self.connect_timeout,
                    http2=True,
                    follow_redirects=True,
                    headers={"User-Agent": "FFTechAudit/1.0"}
                ) as insecure:
                    await insecure.get(url)
                    return {"status": "WARNING", "detail": "SSL_BYPASSED", "error_code": "SSL_001"}
            except (httpx.ConnectTimeout, httpx.ReadTimeout):
                return {"status": "FAILURE", "detail": "TIMEOUT", "error_code": "NET_TIMEOUT"}
            except Exception:
                return {"status": "FAILURE", "detail": "OFFLINE", "error_code": "NET_404"}
        except Exception:
            return {"status": "FAILURE", "detail": "OFFLINE", "error_code": "NET_404"}

    async def fetch_performance(self, url: str) -> Optional[AuditMetrics]:
        """
        Estimate metrics using only Python & HTML parsing:
          - TTFB and total time via streaming
          - HTML complexity via tag counting
          - FCP/LCP (estimates), CLS "N/A"
          - overall_score in [0,1]
        """
        try:
            async with httpx.AsyncClient(
                verify=self.ssl_context,
                timeout=self.fetch_timeout,
                http2=True,
                headers={"User-Agent": "FFTechAudit/1.0"},
            ) as client:
                status_code, ttfb_s, total_time_s, content, final_url, headers = await _fetch_with_timings(
                    client, url, max_bytes=self.max_html_bytes
                )
        except httpx.HTTPError as e:
            logger.warning("HTTP error during fetch_performance(%s): %s", url, e)
            return None
        except Exception as e:
            logger.exception("Unexpected error during fetch_performance(%s): %s", url, e)
            return None

        html_kb, scripts, stylesheets, images, dom_nodes = _analyze_html(content)
        fcp_s, lcp_s = _estimate_fcp_lcp(ttfb_s, total_time_s, html_kb, scripts, stylesheets, images)
        overall = _estimate_overall_score(
            ttfb_s=ttfb_s,
            total_time_s=total_time_s,
            html_kb=html_kb,
            scripts=scripts,
            stylesheets=stylesheets,
            status_code=status_code,
        )

        metrics = AuditMetrics(
            overall_score=overall,
            fcp=_format_seconds_est(fcp_s),
            lcp=_format_seconds_est(lcp_s),
            cls="N/A",
        )
        # Attach some internal details for category scoring (returned via run_full_audit)
        metrics._internal = {  # type: ignore[attr-defined]
            "status_code": status_code,
            "final_url": final_url,
            "headers": {},  # keep light in object; headers used in run_full_audit
            "ttfb_s": ttfb_s,
            "total_time_s": total_time_s,
            "html_kb": html_kb,
            "scripts": scripts,
            "stylesheets": stylesheets,
            "images": images,
            "dom_nodes": dom_nodes,
        }
        # We can't put headers onto pydantic model (not needed); return metrics, headers separately
        metrics._headers = {}  # type: ignore[attr-defined]
        return metrics

    def _compute_category_scores(
        self,
        connectivity: Dict[str, Any],
        perf_internal: Dict[str, Any],
        headers: Dict[str, str],
        final_url: str,
        overall_score: float,
    ) -> Dict[str, float]:
        """
        Compute UI category scores (0..100): performance, ux, connectivity, security.
        """
        # Performance (from overall)
        performance_pct = round(overall_score * 100, 2)

        # UX: penalize heavy DOM/JS/CSS/images, reward smaller pages
        dom_nodes = float(perf_internal.get("dom_nodes", 0))
        scripts = float(perf_internal.get("scripts", 0))
        styles = float(perf_internal.get("stylesheets", 0))
        images = float(perf_internal.get("images", 0))
        html_kb = float(perf_internal.get("html_kb", 0.0))

        s_dom = _score_linear(dom_nodes, good=700.0, bad=5000.0)      # fewer nodes better
        s_js = _score_linear(scripts, good=5.0, bad=40.0)             # fewer scripts better
        s_css = _score_linear(styles, good=3.0, bad=20.0)             # fewer css better
        s_img = _score_linear(images, good=10.0, bad=120.0)           # fewer images better
        s_size = _score_linear(html_kb, good=200.0, bad=3000.0)       # smaller HTML better
        ux = _clamp(0.25*s_dom + 0.25*s_js + 0.15*s_css + 0.15*s_img + 0.20*s_size, 0.0, 1.0)
        ux_pct = round(ux * 100, 2)

        # Connectivity: status + TTFB
        conn_status = connectivity.get("status")
        base = 1.0 if conn_status == "SUCCESS" else (0.7 if conn_status == "WARNING" else 0.1)
        ttfb_s = float(perf_internal.get("ttfb_s", 2.0))
        s_ttfb = _score_linear(ttfb_s, good=0.25, bad=2.5)
        connectivity_score = _clamp(0.6*base + 0.4*s_ttfb, 0.0, 1.0)
        connectivity_pct = round(connectivity_score * 100, 2)

        # Security: headers + HTTPS + connectivity
        security = _security_score_from_headers(
            status=conn_status or "FAILURE",
            headers=headers,
            final_url=final_url or "",
        )
        security_pct = round(security * 100, 2)

        return {
            "performance": performance_pct,
            "ux": ux_pct,
            "connectivity": connectivity_pct,
            "security": security_pct,
        }

    async def run_full_audit(self, url: str) -> Dict[str, Any]:
        """
        Orchestrate the audit:
          - Normalizes URL to https:// if missing.
          - Runs connectivity + performance concurrently.
          - Computes category scores for UI radar chart.
          - Produces offline AI summary.
        """
        if not url.lower().startswith(("http://", "https://")):
            url = f"https://{url}"

        start_time = datetime.now(timezone.utc)

        # Run tasks concurrently
        conn_task = asyncio.create_task(self.validate_connectivity(url))

        # For headers & final URL we need a fetch; we do a single fetch that will be reused
        # in performance estimation as well to avoid double work. For simplicity, we reuse
        # fetch_performance (which streams content). For security score, we need headers,
        # so fetch headers again quickly with HEAD/GET small if needed.
        perf_task = asyncio.create_task(self.fetch_performance(url))

        connectivity = await conn_task
        perf = await perf_task

        # If performance is None, fill safe defaults
        if perf is None:
            report: Dict[str, Any] = {
                "url": url,
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "duration": round((datetime.now(timezone.utc) - start_time).total_seconds(), 2),
                },
                "connectivity": connectivity,
                "performance": None,
                "category_scores": {
                    "performance": 0.0,
                    "ux": 0.0,
                    "connectivity": 0.0 if connectivity["status"] == "FAILURE" else (70.0 if connectivity["status"] == "WARNING" else 90.0),
                    "security": 20.0 if connectivity["status"] != "FAILURE" else 0.0,
                },
                "score": 0.0,
                "health_index": 0,
            }
            report["ai_summary"] = await self.ai_service.generate_audit_summary(report)
            return report

        # We need headers and final_url for security; do a quick HEAD (non-blocking)
        headers: Dict[str, str] = {}
        final_url = url
        try:
            async with httpx.AsyncClient(
                verify=self.ssl_context,
                timeout=10.0,
                http2=True,
                follow_redirects=True,
                headers={"User-Agent": "FFTechAudit/1.0"},
            ) as client:
                resp = await client.head(url)
                headers = {k: v for k, v in resp.headers.items()}
                final_url = str(resp.url)
        except Exception:
            # Ignore header probe failures; security score will fall back on connectivity
            headers = {}
            final_url = url

        # Internal details collected during performance estimation
        internal = getattr(perf, "_internal", {})
        internal = dict(internal) if isinstance(internal, dict) else {}
        internal["final_url"] = final_url  # ensure present

        # Compute category scores
        category_scores = self._compute_category_scores(
            connectivity=connectivity,
            perf_internal=internal,
            headers=headers,
            final_url=final_url,
            overall_score=float(perf.overall_score),
        )

        score = round(float(perf.overall_score) * 100.0, 2)
        health_index = int(round(score))

        report = {
            "url": url,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration": 0.0,
            },
            "connectivity": connectivity,
            "performance": perf.model_dump(),
            "category_scores": category_scores,
            "score": score,
            "health_index": health_index,
        }

        report["ai_summary"] = await self.ai_service.generate_audit_summary(report)
        report["metadata"]["duration"] = round((datetime.now(timezone.utc) - start_time).total_seconds(), 2)

        return report
