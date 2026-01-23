
# app/audit/grader.py
"""
International‑quality, API‑independent website grading.

This module provides a robust, async WebsiteGrader that:
- Does NOT depend on external scoring APIs (e.g., PSI).
- Uses pure Python + httpx to fetch the page and estimate key timings.
- Produces stable, JSON‑serializable outputs compatible with existing callers.
- Preserves public method signatures and output structure.

Notes:
- True Lighthouse metrics (FCP, LCP, CLS) require a headless browser; here we
  provide reasonable, clearly labeled *estimates* based on network timings and
  HTML characteristics so you can operate without external APIs.
- If an external AI summarizer is unavailable, a local summary is generated.
"""

from __future__ import annotations

import asyncio
import logging
import os
import ssl
import certifi
import httpx
from time import perf_counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Dict, Any, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

# Keep import to preserve existing dependency surface; we will gracefully fall back if it fails
try:
    from app.services.ai_service import AIService  # type: ignore
except Exception:  # pragma: no cover
    AIService = None  # Fallback handled below

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
    """Lightweight HTML tag counter for basic complexity signals."""
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
            # Count only CSS links
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


def _score_linear(value: float, good: float, bad: float) -> float:
    """
    Convert a metric to 0..1 where 'good' → 1 and 'bad' → 0 with linear interpolation.
    Handles both higher-is-better (when good > bad) and lower-is-better (when good < bad).
    """
    if good == bad:
        return 1.0
    # Normalize to lower-is-better by flipping if necessary
    if good > bad:
        # higher-is-better: flip values
        value, good, bad = -value, -good, -bad
    t = (value - good) / (bad - good)
    return _clamp(1.0 - t, 0.0, 1.0)


def _format_seconds_est(seconds: Optional[float]) -> str:
    if seconds is None:
        return "N/A"
    return f"{seconds:.2f} s (est.)"


async def _fetch_with_timings(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_bytes: int = 1_048_576,  # Read up to 1 MiB for quick analysis
) -> Tuple[int, float, float, bytes, str]:
    """
    Stream the URL to measure:
      - TTFB (s): time to first response chunk
      - total_time (s): time to read stream (or until max_bytes)
      - status_code
      - content (partial up to max_bytes)
      - final_url (after redirects)
    """
    t_start = perf_counter()
    status_code = 0
    ttfb_s: Optional[float] = None
    total_bytes = 0
    content_chunks: list[bytes] = []
    final_url = url

    async with client.stream("GET", url, follow_redirects=True) as resp:
        status_code = resp.status_code
        final_url = str(resp.url)
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

    return status_code, (ttfb_s or total_time), total_time, b"".join(content_chunks), final_url


def _estimate_fcp_lcp(
    ttfb_s: float,
    total_time_s: float,
    html_kb: float,
    scripts: int,
    stylesheets: int,
    images: int,
) -> Tuple[float, float]:
    """
    Heuristic estimates for FCP/LCP without a real browser:
      - FCP ≈ TTFB + parsing & minimal render time (depends on HTML size and blocking resources)
      - LCP ≈ max(FCP, total_time) + small image penalty
    Tuned conservatively to avoid overpromising.
    """
    # Parsing/render penalty: ~1.5ms per KB + 40ms per script + 20ms per stylesheet
    parse_penalty = 0.0015 * html_kb + 0.04 * scripts + 0.02 * stylesheets
    fcp = ttfb_s + parse_penalty
    # Image penalty: 30ms per image (bounded)
    image_penalty = 0.03 * min(images, 30)
    lcp = max(fcp, total_time_s) + image_penalty
    # Clamp to reasonable bounds
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
    Blend several subscores into a single 0..1 metric:
      - TTFB      (weight 0.25): 0.2s → 1.0, 2.0s → 0.0
      - Total     (weight 0.35): 2.0s → 1.0, 10s  → 0.0
      - Size      (weight 0.20): 150KB → 1.0, 2000KB → 0.0
      - Scripts   (weight 0.10):   5   → 1.0,   40   → 0.0
      - CSS       (weight 0.10):   3   → 1.0,   20   → 0.0
    Non-2xx/3xx statuses incur a heavy penalty.
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

    # Penalize bad HTTP statuses
    if not (200 <= status_code < 400):
        base *= 0.2

    return _clamp(base, 0.0, 1.0)


def _analyze_html(content: bytes) -> Tuple[float, int, int, int, int]:
    """
    Analyze up to 1 MiB of HTML and return:
      (html_kb, scripts, stylesheets, images, dom_nodes)
    """
    # Best effort: attempt to decode using utf-8 with fallback
    text: str
    try:
        text = content.decode("utf-8", errors="ignore")
    except Exception:
        text = ""

    parser = _TagCounter()
    try:
        parser.feed(text)
    except Exception:
        # HTML may be partial; counts are still indicative
        pass

    html_kb = len(content) / 1024.0
    return html_kb, parser.scripts, parser.stylesheets, parser.images, parser.dom_nodes


def _local_ai_summary(report: Dict[str, Any]) -> str:
    """
    Pure-Python, offline summary generator to avoid external AI dependency.
    """
    perf = report.get("performance") or {}
    conn = report.get("connectivity") or {}
    score = report.get("score", 0)

    lines = []
    lines.append(f"Audit summary for {report.get('url')}:")
    lines.append(f"- Overall score: {score:.2f}/100")
    if perf:
        lines.append(f"- Estimated FCP: {perf.get('fcp', 'N/A')}")
        lines.append(f"- Estimated LCP: {perf.get('lcp', 'N/A')}")
        lines.append(f"- CLS (est.): {perf.get('cls', 'N/A')}")
    if conn:
        st = conn.get("status")
        dt = conn.get("detail")
        lines.append(f"- Connectivity: {st} ({dt})")
    lines.append("Recommendations:")
    if score < 85:
        lines.append("• Reduce total page size and number of blocking scripts.")
        lines.append("• Optimize server response time (TTFB) and enable caching/HTTP/2.")
        lines.append("• Compress and lazy-load images; inline critical CSS.")
    else:
        lines.append("• Great performance. Maintain budgets and CI checks to prevent regressions.")
    return "\n".join(lines)


# ------------------------------
# Public Grader
# ------------------------------
class WebsiteGrader:
    """
    Drop-in replacement that avoids external scoring APIs.
    - validate_connectivity(): checks reachability with secure/insecure fallback.
    - fetch_performance(): estimates metrics from network timings and HTML characteristics.
    - run_full_audit(): orchestrates tasks and returns a stable, JSON-serializable report.

    Public signatures and output keys are preserved for compatibility.
    """

    def __init__(self) -> None:
        # Keep env var read to preserve surface; not used for any API calls
        self.api_key = os.getenv("PSI_API_KEY")
        self.psi_endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"  # preserved attribute
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.ai_service = AIService() if AIService else None

        # Tunables
        self.connect_timeout = 15.0
        self.fetch_timeout = 45.0
        self.max_html_bytes = 1_048_576  # 1 MiB

    async def validate_connectivity(self, url: str) -> Dict[str, Any]:
        """
        Try HTTPS first; on SSL errors fall back to insecure fetch and label accordingly.
        Returns:
          { "status": "SUCCESS"|"WARNING"|"FAILURE", "detail": str, "error_code": Optional[str] }
        """
        # HTTPS attempt
        try:
            async with httpx.AsyncClient(
                verify=self.ssl_context,
                timeout=self.connect_timeout,
                http2=True,
                follow_redirects=True,
                headers={"User-Agent": "FFTechAudit/1.0"}
            ) as client:
                resp = await client.get(url)
                # Reachable with SSL
                return {"status": "SUCCESS", "detail": "Secure", "error_code": None}
        except (httpx.ConnectTimeout, httpx.ReadTimeout):
            return {"status": "FAILURE", "detail": "TIMEOUT", "error_code": "NET_TIMEOUT"}
        except httpx.HTTPError:
            # Try HTTP without SSL verification
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
        Estimate performance metrics using only Python:
          - TTFB and total transfer time via streaming.
          - HTML complexity via tag counting (scripts, images, stylesheets, DOM nodes).
          - FCP/LCP as heuristics; CLS reported as 'N/A' (estimation only).
          - overall_score in [0,1] blended from subscores.

        Returns AuditMetrics or None on irrecoverable errors.
        """
        try:
            async with httpx.AsyncClient(
                verify=self.ssl_context,
                timeout=self.fetch_timeout,
                http2=True,
                headers={"User-Agent": "FFTechAudit/1.0"},
            ) as client:
                status_code, ttfb_s, total_time_s, content, final_url = await _fetch_with_timings(
                    client, url, max_bytes=self.max_html_bytes
                )
        except httpx.HTTPError as e:
            logger.warning("HTTP error during fetch_performance(%s): %s", url, e)
            return None
        except Exception as e:  # pragma: no cover
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
            cls="N/A",  # CLS cannot be reliably computed without rendering; keep string per schema
        )
        return metrics

    async def run_full_audit(self, url: str) -> Dict[str, Any]:
        """
        Orchestrates the audit:
          - Normalizes URL (prepend https:// if missing).
          - Runs connectivity + performance concurrently.
          - Assembles the report with identical keys expected by callers.
          - Generates AI summary if available, else local offline summary.

        Returns:
          {
            "url": str,
            "metadata": {"timestamp": iso8601, "duration": seconds_float},
            "connectivity": {...},
            "performance": {...} | None,
            "score": float (0..100),
            "ai_summary": str
          }
        """
        # Normalize URL (preserve existing behavior)
        if not url.lower().startswith(("http://", "https://")):
            url = f"https://{url}"

        start_time = datetime.now(timezone.utc)

        # Run tasks concurrently
        conn_task = asyncio.create_task(self.validate_connectivity(url))
        perf_task = asyncio.create_task(self.fetch_performance(url))
        conn_res, perf_res = await asyncio.gather(conn_task, perf_task)

        report: Dict[str, Any] = {
            "url": url,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration": 0.0,
            },
            "connectivity": conn_res,
            "performance": perf_res.model_dump() if perf_res else None,
            "score": round((perf_res.overall_score * 100), 2) if perf_res else 0.0,
        }

        # Try external AI summarizer if available; otherwise fall back to local summary
        try:
            if self.ai_service and hasattr(self.ai_service, "generate_audit_summary"):
                # If external service exists but fails, fall back gracefully
                summary = await self.ai_service.generate_audit_summary(report)  # type: ignore[attr-defined]
            else:
                summary = _local_ai_summary(report)
        except Exception as e:
            logger.warning("AI summary service unavailable, using local summary: %s", e)
            summary = _local_ai_summary(report)

        report["ai_summary"] = summary
        report["metadata"]["duration"] = round(
            (datetime.now(timezone.utc) - start_time).total_seconds(), 2
        )
        return report
