
# app/audit/grader.py
from __future__ import annotations

import os
import asyncio
import random
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import aiohttp
from aiohttp import ClientResponse, ClientSession


# -----------------------------
# Configuration
# -----------------------------
PSI_API_KEY: Optional[str] = os.getenv("PSI_API_KEY")
PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# Default categories allowed by PSI (note: "best-practices" is hyphenated)
DEFAULT_CATEGORIES: Tuple[str, ...] = ("performance", "seo", "accessibility", "best-practices")

# Timeouts and retry behavior
REQUEST_TIMEOUT_SECONDS = 60
MAX_RETRIES = 4                       # total attempts = 1 initial + MAX_RETRIES
INITIAL_BACKOFF_SECONDS = 0.8         # base backoff
BACKOFF_MULTIPLIER = 2.0              # exponential growth
JITTER_RANGE = (0.0, 0.333)           # add random jitter to avoid thundering herd

# Optional concurrency limit for parallel audits (tune as needed)
_CONCURRENCY_LIMIT = int(os.getenv("AUDIT_CONCURRENCY_LIMIT", "5"))
_semaphore = asyncio.Semaphore(_CONCURRENCY_LIMIT)


# -----------------------------
# Exceptions
# -----------------------------
class AuditError(Exception):
    """High-level error raised by the audit module."""


class PSIRequestError(AuditError):
    """Represents a non-successful response from the PSI API (4xx/5xx)."""

    def __init__(self, status: int, message: str, body: Optional[Mapping[str, Any]] = None):
        super().__init__(f"PSI request failed with status={status}: {message}")
        self.status = status
        self.body = body or {}


class PSIParseError(AuditError):
    """Raised when the PSI response cannot be parsed for expected fields."""


# -----------------------------
# Utilities
# -----------------------------
def _validate_categories(categories: Optional[Iterable[str]]) -> List[str]:
    if not categories:
        return list(DEFAULT_CATEGORIES)
    allowed = set(DEFAULT_CATEGORIES)
    sanitized: List[str] = []
    for c in categories:
        if c in allowed:
            sanitized.append(c)
        else:
            # Silently ignore unknown categories; alternatively raise
            # raise ValueError(f"Unknown PSI category: {c}")
            pass
    return sanitized or list(DEFAULT_CATEGORIES)


def _score_to_pct(value: Optional[float]) -> Optional[float]:
    """Lighthouse scores are in [0, 1]; convert to [0, 100] if present."""
    if value is None:
        return None
    try:
        return round(float(value) * 100.0, 2)
    except (TypeError, ValueError):
        return None


def _extract_scores(data: Mapping[str, Any], categories: Iterable[str]) -> Dict[str, Optional[float]]:
    """
    Safely extract category scores from PSI data. Returns a dict like:
    { 'performance': 92.0, 'seo': 88.0, 'accessibility': None, 'best_practices': 95.0 }
    Missing categories become None. The 'best-practices' category key is normalized to 'best_practices'.
    """
    # Navigate defensively
    lighthouse = (
        data.get("lighthouseResult", {}) if isinstance(data, Mapping) else {}
    )
    cats = lighthouse.get("categories", {}) if isinstance(lighthouse, Mapping) else {}

    out: Dict[str, Optional[float]] = {}
    for cat in categories:
        key_in_response = cat  # e.g. 'best-practices'
        node = cats.get(key_in_response, {})
        raw = node.get("score") if isinstance(node, Mapping) else None

        normalized_name = "best_practices" if cat == "best-practices" else cat
        out[normalized_name] = _score_to_pct(raw)
    return out


def _compute_final_score(mobile_scores: Mapping[str, Optional[float]],
                         desktop_scores: Mapping[str, Optional[float]]) -> float:
    """
    Average all available (non-None) scores across mobile + desktop categories.
    Returns 0.0 if nothing is available.
    """
    values: List[float] = []
    for d in (mobile_scores, desktop_scores):
        for v in d.values():
            if isinstance(v, (int, float)):
                values.append(float(v))
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


async def _read_json(resp: ClientResponse) -> Mapping[str, Any]:
    try:
        return await resp.json()
    except Exception as e:
        text = await resp.text()
        raise PSIParseError(f"Failed to parse PSI JSON. Status={resp.status}, Error={e}, Body={text[:500]}") from e


async def _backoff_sleep(attempt: int) -> None:
    # attempt starts from 0 for the first retry (after the initial failure)
    backoff = INITIAL_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** attempt)
    jitter = random.uniform(*JITTER_RANGE)
    await asyncio.sleep(backoff + jitter)


# -----------------------------
# Core HTTP Call
# -----------------------------
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
    Fire a single PSI request with retries/backoff for transient failures (429/5xx, timeouts).
    """
    cats = _validate_categories(categories)
    api_key = api_key or PSI_API_KEY  # allow override per call

    params: List[Tuple[str, str]] = [
        ("url", url),
        ("strategy", strategy),
    ]
    # PSI supports multiple 'category' params
    for c in cats:
        params.append(("category", c))

    if api_key:
        params.append(("key", api_key))
    if locale:
        params.append(("locale", locale))

    # Retry loop
    attempt = 0
    while True:
        try:
            async with session.get(PSI_ENDPOINT, params=params, timeout=timeout_seconds) as resp:
                if 200 <= resp.status < 300:
                    return await _read_json(resp)
                # Retry on 429/5xx, otherwise raise immediately
                if resp.status in (429, 500, 502, 503, 504):
                    body = await _read_json(resp)
                    if attempt < MAX_RETRIES:
                        await _backoff_sleep(attempt)
                        attempt += 1
                        continue
                    raise PSIRequestError(resp.status, "Max retries exceeded", body)
                else:
                    body = await _read_json(resp)
                    raise PSIRequestError(resp.status, "Non-retryable PSI error", body)
        except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as e:
            if attempt < MAX_RETRIES:
                await _backoff_sleep(attempt)
                attempt += 1
                continue
            raise PSIRequestError(0, f"Network/timeout error after retries: {e}") from e


# -----------------------------
# Public API
# -----------------------------
async def run_audit(
    url: str,
    *,
    categories: Optional[Iterable[str]] = None,
    locale: Optional[str] = None,
    timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run a dual-strategy PSI audit (mobile + desktop) and return a JSON-serializable payload.

    Returns:
    {
        "url": "...",
        "scores": {
            "mobile": { "performance": 92.0, "seo": 88.0, "accessibility": 97.0, "best_practices": 95.0 },
            "desktop": { ... }
        },
        "final_score": 93.25,
        "engine": "Google PSI + Lighthouse",
        "metrics_count": 200,    # retained for compatibility; PSI is vast—this is an indicative count
        "meta": {
            "locale": "en",
            "categories": ["performance", "seo", "accessibility", "best-practices"]
        }
    }
    """
    if not isinstance(url, str) or not url.strip():
        raise AuditError("A non-empty URL string is required.")

    cats = _validate_categories(categories)

    async with _semaphore:  # limit concurrency if many audits run in parallel
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout, raise_for_status=False) as session:
            # Run mobile/desktop concurrently with robust fetching
            mobile_data, desktop_data = await asyncio.gather(
                _fetch_psi(session, url, "mobile", categories=cats, locale=locale, api_key=api_key, timeout_seconds=timeout_seconds),
                _fetch_psi(session, url, "desktop", categories=cats, locale=locale, api_key=api_key, timeout_seconds=timeout_seconds),
            )

    # Extract scores defensively
    mobile_scores = _extract_scores(mobile_data, cats)
    desktop_scores = _extract_scores(desktop_data, cats)

    final_score = _compute_final_score(mobile_scores, desktop_scores)

    payload: Dict[str, Any] = {
        "url": url,
        "scores": {
            "mobile": mobile_scores,
            "desktop": desktop_scores,
        },
        "final_score": final_score,
        "engine": "Google PSI + Lighthouse",
        "metrics_count": 200,  # keep for UX; not a hard count
        "meta": {
            "locale": locale,
            "categories": list(cats),
        },
    }
    return payload
