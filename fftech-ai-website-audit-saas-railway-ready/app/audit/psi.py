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
    """Clamp PSI scores to 0..100"""
    try:
        if v is None:
            return 0.0
        v = float(v)
        if v <= 1.0:
            v *= 100.0
        return max(0.0, min(100.0, v))
    except Exception:
        return 0.0


async def _one_attempt(
    session: aiohttp.ClientSession,
    url: str,
    api_key: str,
    strategy: str,
) -> Tuple[Optional[Dict[str, float]], Optional[float]]:
    """Perform a single PSI request"""
    categories = ["performance", "seo", "accessibility", "best-practices"]
    params = [("url", url), ("strategy", strategy)] + [("category", c) for c in categories]
    if api_key:
        params.append(("key", api_key))

    async with session.get(PAGESPEED_API, params=params) as resp:
        if resp.status == 429:
            ra = resp.headers.get("Retry-After")
            retry_after = float(ra) if ra else 2.0
            logger.warning("[PSI] 429 for %s, retry-after=%.2fs", url, retry_after)
            return None, retry_after
        if resp.status >= 500:
            logger.warning("[PSI] %s returned HTTP %s for %s", PAGESPEED_API, resp.status, url)
            return None, None
        if resp.status != 200:
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


# --- New: Python-based Pre-Audit ---
def python_library_audit(url: str) -> Dict[str, float]:
    """
    Perform initial checks using local Python libraries (world-class pre-audit):
    - Check URL validity
    - Check network accessibility
    - Placeholder for additional Python-based static checks
    """
    import validators
    import requests

    result = DEFAULT_RESULT.copy()
    target = _normalize_url(url)

    if not target or not validators.url(target):
        logger.error("[PRE-AUDIT] Invalid URL: %s", url)
        return result

    # Check if page is reachable
    try:
        resp = requests.head(target, timeout=5)
        if resp.status_code >= 400:
            logger.warning("[PRE-AUDIT] Page returned HTTP %s for %s", resp.status_code, target)
        else:
            # Increment SEO/accessibility placeholder
            result["seo"] += 20.0
            result["accessibility"] += 10.0
    except Exception as e:
        logger.warning("[PRE-AUDIT] Failed to reach page %s: %s", target, e)

    return result


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
    Combined audit:
    1. Pre-audit using Python libraries (local, fast)
    2. External PSI/PageSpeed Insights (async, optional)
    """
    # Step 1: Pre-Audit
    result = python_library_audit(url)

    # Step 2: If PSI API key provided, fetch external metrics
    if api_key:
        target = _normalize_url(url)
        if not target:
            return result

        client_timeout = ClientTimeout(
            total=per_attempt_timeout,
            sock_connect=min(5.0, per_attempt_timeout),
            sock_read=per_attempt_timeout,
        )
        start = asyncio.get_event_loop().time()
        deadline = start + max(0.1, overall_timeout)
        base_backoff = 1.0
        max_backoff = 6.0

        async with aiohttp.ClientSession(timeout=client_timeout, raise_for_status=False) as session:
            for attempt in range(1, max_attempts + 1):
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    logger.warning("[PSI] Overall timeout reached before attempt %d for %s", attempt, target)
                    break
                try:
                    res, retry_after = await asyncio.wait_for(
                        _one_attempt(session, target, api_key, strategy),
                        timeout=min(per_attempt_timeout + 1.0, max(0.1, remaining)),
                    )
                    if res:
                        # Merge PSI results with pre-audit (prefer PSI metrics)
                        result.update(res)
                        return result
                    if attempt < max_attempts:
                        sleep_for = retry_after if retry_after else min(max_backoff, base_backoff * (2 ** (attempt - 1)))
                        sleep_for = max(0.1, min(sleep_for, deadline - asyncio.get_event_loop().time()))
                        await asyncio.sleep(sleep_for)
                except asyncio.TimeoutError:
                    logger.warning("[PSI] Attempt %d timed out for %s", attempt, target)
                except ClientError as ce:
                    logger.warning("[PSI] ClientError on attempt %d for %s: %s", attempt, target, ce)
                except Exception as e:
                    logger.exception("[PSI] Unexpected error on attempt %d for %s: %s", attempt, target, e)

    return result
