
# app/audit/grader.py
from __future__ import annotations

import os
import asyncio
import random
import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import aiohttp
from aiohttp import ClientResponse, ClientSession

logger = logging.getLogger(__name__)

# --------------------------------------
# Configuration
# --------------------------------------
PSI_API_KEY: Optional[str] = os.getenv("PSI_API_KEY")
PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# Allowed Lighthouse categories
DEFAULT_CATEGORIES: Tuple[str, ...] = (
    "performance",
    "seo",
    "accessibility",
    "best-practices",
)

# HTTP timeouts & retry behavior
REQUEST_TIMEOUT_SECONDS = int(os.getenv("PSI_REQUEST_TIMEOUT", "60"))
MAX_RETRIES = int(os.getenv("PSI_MAX_RETRIES", "4"))           # 1 initial + up to 4 retries
INITIAL_BACKOFF_SECONDS = float(os.getenv("PSI_BACKOFF_BASE", "0.8"))
BACKOFF_MULTIPLIER = float(os.getenv("PSI_BACKOFF_MULTIPLIER", "2.0"))
JITTER_MIN = float(os.getenv("PSI_BACKOFF_JITTER_MIN", "0.0"))
JITTER_MAX = float(os.getenv("PSI_BACKOFF_JITTER_MAX", "0.333"))

# Concurrency limit (protect your quotas and server resources)
_CONCURRENCY_LIMIT = int(os.getenv("AUDIT_CONCURRENCY_LIMIT", "5"))
_semaphore = asyncio.Semaphore(_CONCURRENCY_LIMIT)


# --------------------------------------
# Exceptions
# --------------------------------------
class AuditError(Exception):
    """High-level error raised by the audit module."""


class PSIRequestError(AuditError):
    """Non-successful response or unrecoverable error from PSI API."""

    def __init__(self, status: int, message: str, body: Optional[Mapping[str, Any]] = None):
        super().__init__(f"PSI request failed with status={status}: {message}")
        self.status = status
        self.body = body or {}


class PSIParseError(AuditError):
    """Raised when the PSI response cannot be parsed for expected fields."""


# --------------------------------------
# Helpers
# --------------------------------------
def _validate_categories(categories: Optional[Iterable[str]]) -> List[str]:
    if not categories:
        return list(DEFAULT_CATEGORIES)
    allowed = set(DEFAULT_CATEGORIES)
    out: List[str] = []
    for c in categories:
        if c in allowed:
            out.append(c)
    return out or list(DEFAULT_CATEGORIES)


def _score_to_pct(value: Optional[float]) -> Optional[float]:
    """Lighthouse category scores are [0,1]; convert to [0,100] with 2 decimals."""
    if value is None:
        return None
    try:
        return round(float(value) * 100.0, 2)
    except (TypeError, ValueError):
        return None


def _ms_to_seconds(value_ms: Optional[float]) -> Optional[float]:
    """Convert milliseconds to seconds with 2 decimals."""
    if value_ms is None:
        return None
    try:
        return round(float(value_ms) / 1000.0, 2)
    except (TypeError, ValueError):
        return None


def _safe_get(mapping: Mapping[str, Any], *path: str, default: Any = None) -> Any:
    """Safely navigate nested dicts."""
    cur: Any = mapping
    for key in path:
        if not isinstance(cur, Mapping):
            return default
        cur = cur.get(key, default)
        if cur is default:
            return default
    return cur


def _extract_scores(data: Mapping[str, Any], categories: Iterable[str]) -> Dict[str, Optional[float]]:
    """
    Extract category-level scores into a flat dict with normalized names
    (e.g., "best-practices" -> "best_practices").
    """
    cats = _safe_get(data, "lighthouseResult", "categories", default={})
    out: Dict[str, Optional[float]] = {}
    for cat in categories:
        normalized = "best_practices" if cat == "best-practices" else cat
        score = _safe_get(cats, cat, "score", default=None)
        out[normalized] = _score_to_pct(score)
    return out


def _extract_metrics(data: Mapping[str, Any]) -> Dict[str, Optional[float]]:
    """
    Extract key performance metrics from Lighthouse audits.

    Returns seconds (s) for time metrics and unitless for CLS.
    Keys:
      - fcp (First Contentful Paint)
      - lcp (Largest Contentful Paint)
      - cls (Cumulative Layout Shift)
      - tbt (Total Blocking Time)
      - inp (Interaction to Next Paint)
      - tti (Time to Interactive)
      - speed_index
      - ttfb (Server Response Time)
    """
    audits = _safe_get(data, "lighthouseResult", "audits", default={})

    def nv(key: str) -> Optional[float]:
        return _safe_get(audits, key, "numericValue", default=None)

    # milliseconds → seconds (except CLS which is unitless)
    fcp = _ms_to_seconds(nv("first-contentful-paint"))
    lcp = _ms_to_seconds(nv("largest-contentful-paint"))
    cls = _safe_get(audits, "cumulative-layout-shift", "numericValue", default=None)
    tbt = _ms_to_seconds(nv("total-blocking-time"))
    # INP: experimental key
    inp = _ms_to_seconds(nv("experimental-interaction-to-next-paint"))
    tti = _ms_to_seconds(nv("interactive"))
    speed_index = _ms_to_seconds(nv("speed-index"))
    ttfb = _ms_to_seconds(nv("server-response-time"))

    return {
        "fcp": fcp,
        "lcp": lcp,
        "cls": None if cls is None else round(float(cls), 3),
        "tbt": tbt,
        "inp": inp,
        "tti": tti,
        "speed_index": speed_index,
        "ttfb": ttfb,
    }


def _extract_top_opportunities_and_diagnostics(
    data: Mapping[str, Any],
    *,
    top_n: int = 5
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract top opportunities (by 'overallSavingsMs') and key diagnostics.
    """
    audits = _safe_get(data, "lighthouseResult", "audits", default={})
    if not isinstance(audits, Mapping):
        return {"opportunities": [], "diagnostics": []}

    opportunities: List[Dict[str, Any]] = []
    diagnostics: List[Dict[str, Any]] = []

    for audit_key, audit in audits.items():
        if not isinstance(audit, Mapping):
            continue
        details = audit.get("details")
        title = audit.get("title")
        desc = audit.get("description")
        score = audit.get("score")
        display_mode = audit.get("scoreDisplayMode")

        # Opportunities typically have 'opportunity' details and 'overallSavingsMs'
        if isinstance(details, Mapping) and details.get("type") == "opportunity":
            savings_ms = details.get("overallSavingsMs")
            if savings_ms is not None:
                opportunities.append({
                    "id": audit_key,
                    "title": title,
                    "description": desc,
                    "estimated_savings_s": _ms_to_seconds(savings_ms),
                    "score": score,
                })
        else:
            # Diagnostics: pick a subset of informative items
            if display_mode in ("informative", "numeric") and title:
                item: Dict[str, Any] = {
                    "id": audit_key,
                    "title": title,
                    "score": score,
                }
                # Attach a compact numeric value if present
                numeric = audit.get("numericValue")
                unit = audit.get("numericUnit")
                if numeric is not None:
                    item["numeric"] = numeric
                    if unit:
                        item["numeric_unit"] = unit
                diagnostics.append(item)

    # Sort opportunities by savings desc, take top_n
    opportunities.sort(key=lambda x: (x.get("estimated_savings_s") or 0.0), reverse=True)
    if top_n > 0:
        opportunities = opportunities[:top_n]
        diagnostics = diagnostics[:top_n]

    return {"opportunities": opportunities, "diagnostics": diagnostics}


def _compute_final_score(
    mobile_scores: Mapping[str, Optional[float]],
    desktop_scores: Mapping[str, Optional[float]],
) -> float:
    """
    Average all available (non-None) category scores across mobile + desktop.
    Returns 0.0 if none available.
    """
    vals: List[float] = []
    for m in (mobile_scores, desktop_scores):
        for v in m.values():
            if isinstance(v, (int, float)):
                vals.append(float(v))
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def _letter_grade(score: float) -> str:
    """
    Convert 0-100 score to a letter grade (customizable thresholds).
    """
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


async def _read_json(resp: ClientResponse) -> Mapping[str, Any]:
    try:
        return await resp.json()
    except Exception as e:
        text = await resp.text()
        raise PSIParseError(
            f"Failed to parse PSI JSON. Status={resp.status}, Error={e}, Body={text[:1000]}"
        ) from e


async def _backoff_sleep(attempt: int) -> None:
    backoff = INITIAL_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** attempt)
    jitter = random.uniform(JITTER_MIN, JITTER_MAX)
    await asyncio.sleep(backoff + jitter)


# --------------------------------------
# Core HTTP call with retries
# --------------------------------------
async def _fetch_psi(
    session: ClientSession,
    url: str,
    strategy: str,
    *,
    categories: Optional[Iterable[str]] = None,
    locale: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
) -> Mapping[str, Any]:
    """
    Execute one PSI request with retries for transient errors (429/5xx, timeouts).
    For 400 (bad request), raise immediately with the PSI error body (non-retryable).
    """
    cats = _validate_categories(categories)
    api_key = api_key or PSI_API_KEY

    params: List[Tuple[str, str]] = [
        ("url", url),
        ("strategy", strategy),
    ]
    for c in cats:
        params.append(("category", c))
    if api_key:
        params.append(("key", api_key))
    if locale:
        params.append(("locale", locale))

    attempt = 0
    while True:
        try:
            async with session.get(PSI_ENDPOINT, params=params, timeout=timeout_seconds) as resp:
                if 200 <= resp.status < 300:
                    return await _read_json(resp)

                body = await _read_json(resp)

                # Non-retryable bad requests: surface details to caller
                if resp.status == 400:
                    logger.warning(
                        "PSI 400 for url=%s strategy=%s params=%s body=%s",
                        url, strategy, params, str(body)[:1000]
                    )
                    raise PSIRequestError(resp.status, "Non-retryable PSI error", body)

                # Retry on transient errors
                if resp.status in (429, 500, 502, 503, 504):
                    if attempt < MAX_RETRIES:
                        logger.info(
                            "PSI transient error %s for %s (%s). Retrying attempt %s",
                            resp.status, url, strategy, attempt + 1
                        )
                        await _backoff_sleep(attempt)
                        attempt += 1
                        continue
                    raise PSIRequestError(resp.status, "Max retries exceeded", body)

                # Other statuses: treat as non-retryable
                raise PSIRequestError(resp.status, "PSI request failed", body)

        except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as e:
            if attempt < MAX_RETRIES:
                logger.info(
                    "PSI network/timeout for %s (%s). Retrying attempt %s: %s",
                    url, strategy, attempt + 1, e
                )
                await _backoff_sleep(attempt)
                attempt += 1
                continue
            raise PSIRequestError(0, f"Network/timeout error after retries: {e}") from e


# --------------------------------------
# Public API
# --------------------------------------
async def run_audit(
    url: str,
    *,
    categories: Optional[Iterable[str]] = None,
    locale: Optional[str] = None,
    timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
    api_key: Optional[str] = None,
    include_raw_lhr: bool = False,          # include compact raw LHR (optional)
    top_n_insights: int = 5,                # number of top opportunities/diagnostics
) -> Dict[str, Any]:
    """
    Run a dual-strategy PSI audit (mobile + desktop) and return a rich, JSON-serializable payload.

    Returns (example):
    {
      "url": "https://example.com",
      "engine": "Google PSI + Lighthouse",
      "meta": {
        "locale": "en",
        "categories": ["performance", "seo", "accessibility", "best-practices"],
        "lighthouse": {
          "mobile_version": "12.3.0",
          "desktop_version": "12.3.0",
          "mobile_fetch_time": "2026-01-23T10:11:12.345Z",
          "desktop_fetch_time": "2026-01-23T10:11:13.678Z",
          "user_agent_mobile": "...",
          "user_agent_desktop": "..."
        }
      },
      "scores": {
        "mobile":   {"performance": 92.0, "seo": 88.0, "accessibility": 97.0, "best_practices": 95.0},
        "desktop":  { ... }
      },
      "metrics": {
        "mobile":  {"fcp": 1.9, "lcp": 2.7, "cls": 0.04, "tbt": 0.12, "inp": 0.18, "tti": 2.5, "speed_index": 2.1, "ttfb": 0.2},
        "desktop": { ... }
      },
      "insights": {
        "mobile": {
          "opportunities": [
            {"id": "...", "title": "...", "estimated_savings_s": 1.25, "score": 0.35, "description": "..."}
          ],
          "diagnostics": [ ... ]
        },
        "desktop": { ... }
      },
      "final_score": 93.25,
      "grade": "A",
      "metrics_count": 200,
      "raw": {
        "mobile": {...},     # INCLUDED ONLY IF include_raw_lhr=True (compact subset)
        "desktop": {...}
      }
    }
    """
    if not isinstance(url, str) or not url.strip():
        raise AuditError("A non-empty URL string is required.")

    cats = _validate_categories(categories)

    async with _semaphore:
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout, raise_for_status=False) as session:
            mobile_data, desktop_data = await asyncio.gather(
                _fetch_psi(
                    session, url, "mobile",
                    categories=cats, locale=locale, api_key=api_key, timeout_seconds=timeout_seconds
                ),
                _fetch_psi(
                    session, url, "desktop",
                    categories=cats, locale=locale, api_key=api_key, timeout_seconds=timeout_seconds
                ),
            )

    # Scores
    mobile_scores = _extract_scores(mobile_data, cats)
    desktop_scores = _extract_scores(desktop_data, cats)

    # Metrics
    mobile_metrics = _extract_metrics(mobile_data)
    desktop_metrics = _extract_metrics(desktop_data)

    # Insights (top opportunities/diagnostics)
    mobile_insights = _extract_top_opportunities_and_diagnostics(mobile_data, top_n=top_n_insights)
    desktop_insights = _extract_top_opportunities_and_diagnostics(desktop_data, top_n=top_n_insights)

    # Lighthouse/env metadata
    meta = {
        "locale": locale,
        "categories": list(cats),
        "lighthouse": {
            "mobile_version": _safe_get(mobile_data, "lighthouseResult", "lighthouseVersion"),
            "desktop_version": _safe_get(desktop_data, "lighthouseResult", "lighthouseVersion"),
            "mobile_fetch_time": _safe_get(mobile_data, "lighthouseResult", "fetchTime"),
            "desktop_fetch_time": _safe_get(desktop_data, "lighthouseResult", "fetchTime"),
            "user_agent_mobile": _safe_get(mobile_data, "lighthouseResult", "userAgent"),
            "user_agent_desktop": _safe_get(desktop_data, "lighthouseResult", "userAgent"),
        },
    }

    final_score = _compute_final_score(mobile_scores, desktop_scores)
    grade = _letter_grade(final_score)

    payload: Dict[str, Any] = {
        "url": url,
        "engine": "Google PSI + Lighthouse",
        "meta": meta,
        "scores": {
            "mobile": mobile_scores,
            "desktop": desktop_scores,
        },
        "metrics": {
            "mobile": mobile_metrics,
            "desktop": desktop_metrics,
        },
        "insights": {
            "mobile": mobile_insights,
            "desktop": desktop_insights,
        },
        "final_score": final_score,
        "grade": grade,
        "metrics_count": 200,  # retained for UI compatibility; not a strict count
    }

    if include_raw_lhr:
        # Provide a compact raw subset for debugging/transparency.
        def compact_lhr(d: Mapping[str, Any]) -> Dict[str, Any]:
            return {
                "requestedUrl": _safe_get(d, "lighthouseResult", "requestedUrl"),
                "finalUrl": _safe_get(d, "lighthouseResult", "finalUrl"),
                "runWarnings": _safe_get(d, "lighthouseResult", "runWarnings", default=[]),
                "configSettings": _safe_get(d, "lighthouseResult", "configSettings", default={}),
                "environment": _safe_get(d, "lighthouseResult", "environment", default={}),
            }
        payload["raw"] = {
            "mobile": compact_lhr(mobile_data),
            "desktop": compact_lhr(desktop_data),
        }

    return payload
