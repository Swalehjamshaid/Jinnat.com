
# app/audit/psi.py
import asyncio
import logging
from typing import Dict, Tuple, Optional
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientTimeout
from aiohttp.client_exceptions import ClientError

PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

logger = logging.getLogger(__name__)

DEFAULT_RESULT: Dict[str, float] = {
    "performance": 0.0,
    "seo": 0.0,
    "accessibility": 0.0,
    "best_practices": 0.0,
    "lcp": 0.0,
    "cls": 0.0,
}

def _normalize_url(url: str) -> str:
    """Ensure the URL has a scheme. Default to https:// if missing."""
    u = (url or "").strip()
    if not u:
        return ""
    parsed = urlparse(u)
    if not parsed.scheme:
        u = "https://" + u
    return u

def _clamp_score(v: Optional[float]) -> float:
    """PSI returns category score in [0,1]. Convert to 0..100 and clamp."""
    try:
        if v is None:
            return 0.0
        v = float(v)
        # If API already returns 0..100 due to future change, still clamp
        if v <= 1.0:
            v *= 100.0
        return max(0.0, min(100.0, v))
    except Exception:
        return 0.0

def _extract_retry_after(resp: aiohttp.ClientResponse) -> Optional[float]:
    """Get Retry-After seconds if present."""
    ra = resp.headers.get("Retry-After")
    if not ra:
        return None
    try:
        # Could be delta-seconds; PSI uses seconds for 429
        return float(ra)
    except Exception:
        return None

async def _one_attempt(
    session: aiohttp.ClientSession,
    url: str,
    api_key: str,
    strategy: str,
) -> Tuple[Optional[Dict[str, float]], Optional[float]]:
    """
    Perform a single HTTP request to PSI.
    Returns (result, retry_after_seconds).
    retry_after_seconds is set when server asks to rate-limit (e.g., 429).
    """
    categories = ["performance", "seo", "accessibility", "best-practices"]
    params = [
        ("url", url),
        ("strategy", strategy),
    ] + [("category", c) for c in categories]

    if api_key:
        params.append(("key", api_key))

    async with session.get(PAGESPEED_API, params=params) as resp:
        # Handle rate limiting explicitly
        if resp.status == 429:
            ra = _extract_retry_after(resp) or 2.0
            logger.warning("[PSI] 429 for %s, retry-after=%.2fs", url, ra)
            return None, ra

        if resp.status >= 500:
            # Transient server error, retryable
            logger.warning("[PSI] %s returned HTTP %s for %s", PAGESPEED_API, resp.status, url)
            return None, None

        if resp.status != 200:
            # Non-retryable client error (e.g., invalid URL)
            text = await resp.text()
            logger.error("[PSI] HTTP %s for %s. Body: %s", resp.status, url, text[:500])
            return DEFAULT_RESULT.copy(), None

        data = await resp.json()

        lighthouse = data.get("lighthouseResult", {})
        categories_obj = lighthouse.get("categories", {}) or {}
        audits = lighthouse.get("audits", {}) or {}

        result: Dict[str, float] = {
            "performance": _clamp_score(categories_obj.get("performance", {}).get("score")),
            "seo": _clamp_score(categories_obj.get("seo", {}).get("score")),
            "accessibility": _clamp_score(categories_obj.get("accessibility", {}).get("score")),
            "best_practices": _clamp_score(categories_obj.get("best-practices", {}).get("score")),
            "lcp": float(audits.get("largest-contentful-paint", {}).get("numericValue") or 0.0) / 1000.0,
            "cls": float(audits.get("cumulative-layout-shift", {}).get("numericValue") or 0.0),
        }
        return result, None

async def fetch_lighthouse(
    url: str,
    api_key: str,
    strategy: str = "mobile",
    *,
    per_attempt_timeout: float = 8.0,
    max_attempts: int = 3,
    overall_timeout: float = 18.0,
) -> Dict[str, float]:
    """
    Fetch Lighthouse/PageSpeed Insights data asynchronously with strict time bounds.

    Guarantees:
    - Returns within 'overall_timeout' seconds (worst case).
    - Retries with exponential backoff + jitter.
    - Respects Retry-After on 429.
    - Always returns a dict (defaults on failures).

    Args:
        url: Target page URL (scheme optional; https:// will be assumed if missing).
        api_key: Google PSI API key (can be empty; request may still work).
        strategy: "mobile" or "desktop".
        per_attempt_timeout: HTTP total timeout for each request.
        max_attempts: Max number of attempts (including first).
        overall_timeout: Hard cap for the entire operation.
    """
    target = _normalize_url(url)
    if not target:
        logger.error("[PSI] Empty or invalid URL input.")
        return DEFAULT_RESULT.copy()

    # Prepare single session with proper timeouts.
    client_timeout = ClientTimeout(
        # per-attempt budget (connect + read)
        total=per_attempt_timeout,
        sock_connect=min(5.0, per_attempt_timeout),
        sock_read=per_attempt_timeout,
    )

    start = asyncio.get_event_loop().time()
    deadline = start + max(0.1, overall_timeout)

    # Jittered exponential backoff parameters
    base_backoff = 1.0  # seconds
    max_backoff = 6.0

    async with aiohttp.ClientSession(timeout=client_timeout, raise_for_status=False) as session:
        for attempt in range(1, max_attempts + 1):
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                logger.warning("[PSI] Overall timeout reached before attempt %d for %s", attempt, target)
                break

            try:
                # Ensure we don't exceed overall budget per attempt
                try:
                    result, retry_after = await asyncio.wait_for(
                        _one_attempt(session, target, api_key, strategy),
                        timeout=min(per_attempt_timeout + 1.0, max(0.1, remaining)),
                    )
                except asyncio.TimeoutError:
                    logger.warning("[PSI] Attempt %d/%d timed out for %s", attempt, max_attempts, target)
                    result, retry_after = None, None

                # If result computed (either real data or defaults on non-retryable), return it.
                if result is not None:
                    return result

                # Otherwise plan next retry
                if attempt < max_attempts:
                    # Respect Retry-After if present; otherwise exponential backoff with jitter
                    if retry_after is not None:
                        sleep_for = retry_after
                    else:
                        backoff = min(max_backoff, base_backoff * (2 ** (attempt - 1)))
                        # jitter in [0, 0.3*backoff]
                        sleep_for = backoff + (0.3 * backoff) * (asyncio.get_event_loop().time() % 1.0)

                    # Don't sleep past the deadline
                    sleep_for = max(0.1, min(sleep_for, deadline - asyncio.get_event_loop().time()))
                    if sleep_for > 0.1:
                        await asyncio.sleep(sleep_for)
                else:
                    # No more attempts left
                    break

            except ClientError as ce:
                logger.warning("[PSI] ClientError on attempt %d/%d for %s: %s", attempt, max_attempts, target, ce)
                if attempt >= max_attempts:
                    break
            except Exception as e:
                logger.exception("[PSI] Unexpected error on attempt %d/%d for %s: %s", attempt, max_attempts, target, e)
                if attempt >= max_attempts:
                    break

    logger.error("[PSI] Failed to fetch Lighthouse metrics for %s within budget. Returning defaults.", target)
    return DEFAULT_RESULT.copy()
