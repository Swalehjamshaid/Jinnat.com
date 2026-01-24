
# app/audit/psi.py
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# Simple in-memory cache: (url, strategy) -> (expires_at, data)
# For production, consider Redis or your database.
_PSI_CACHE: Dict[Tuple[str, str], Tuple[float, Dict[str, Any]]] = {}

# Tunables
DEFAULT_CONNECT_TIMEOUT = 5.0     # seconds
DEFAULT_READ_TIMEOUT = 20.0       # seconds (PSI can be slow; keep it modest)
DEFAULT_TOTAL_TIMEOUT = 30.0      # seconds overall budget per request
DEFAULT_CACHE_TTL = 300.0         # 5 minutes cache
DEFAULT_MAX_RETRIES = 2           # total attempts = 1 + retries
DEFAULT_BACKOFF_BASE = 0.75       # seconds, exponential

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def _get_api_key(passed_key: Optional[str]) -> Optional[str]:
    if passed_key:
        return passed_key
    # prefer env first to avoid importing settings at import-time
    env_key = os.getenv("PSI_API_KEY")
    if env_key:
        return env_key
    try:
        # Lazy import to avoid cyclic imports
        from ..settings import get_settings
        return get_settings().PSI_API_KEY
    except Exception:
        return None


def _build_params(url: str, strategy: str, api_key: str) -> Dict[str, Any]:
    # Google PSI accepts multiple category params. httpx encodes list as repeated keys.
    return {
        "url": url,
        "key": api_key,
        "strategy": strategy,
        "category": [
            "PERFORMANCE",
            "SEO",
            "ACCESSIBILITY",
            "BEST_PRACTICES",
        ],
    }


def _should_cache(data: Optional[Dict[str, Any]]) -> bool:
    # Cache only successful responses that contain Lighthouse metrics
    if not data:
        return False
    return "lighthouseResult" in data or "loadingExperience" in data


async def _async_fetch_once(
    client: httpx.AsyncClient,
    params: Dict[str, Any],
    total_budget_s: float,
) -> Optional[Dict[str, Any]]:
    # Enforce a soft overall budget using per-request read timeout
    try:
        resp = await client.get(PSI_ENDPOINT, params=params)
        if resp.status_code != 200:
            logger.error("❌ Google PSI Error %s: %s", resp.status_code, resp.text)
            return None
        return resp.json()
    except httpx.ReadTimeout:
        logger.error("⏳ PSI Read timeout.")
        return None
    except httpx.ConnectTimeout:
        logger.error("⏳ PSI Connect timeout.")
        return None
    except Exception as e:
        logger.error("❌ PSI Request failed: %s", e)
        return None


async def _async_fetch_with_retries(
    url: str,
    strategy: str,
    api_key: str,
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
    read_timeout: float = DEFAULT_READ_TIMEOUT,
    total_timeout: float = DEFAULT_TOTAL_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
) -> Optional[Dict[str, Any]]:
    params = _build_params(url, strategy, api_key)
    timeout = httpx.Timeout(
        connect=connect_timeout,
        read=read_timeout,
        write=5.0,
        pool=5.0,
    )
    headers = {
        # Realistic UA can help avoid odd throttling in some environments
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
        attempt = 0
        while True:
            attempt += 1
            remaining = total_timeout - (time.monotonic() - start)
            if remaining <= 0:
                logger.error("⏳ PSI overall budget exceeded (%.1fs).", total_timeout)
                return None

            data = await _async_fetch_once(client, params, remaining)
            if data:
                return data

            if attempt > max_retries + 1:
                return None

            sleep_s = backoff_base * (2 ** (attempt - 1))
            sleep_s = min(sleep_s, max(0.2, remaining / 2))
            await _async_sleep(sleep_s)


async def _async_sleep(seconds: float):
    # Isolated for testability and potential cancellation handling
    await httpx._config.asyncio.sleep(seconds)  # uses asyncio.sleep under the hood


async def async_fetch_psi(
    url: str,
    strategy: str = "desktop",
    api_key: Optional[str] = None,
    cache_ttl: float = DEFAULT_CACHE_TTL,
) -> Optional[Dict[str, Any]]:
    """
    Async PSI fetch with retries, timeouts and in-memory caching.
    Returns parsed JSON or None.
    """
    api_key_resolved = _get_api_key(api_key)
    if not api_key_resolved:
        logger.error("❌ No PSI_API_KEY found. Audit cannot proceed.")
        return None

    cache_key = (url, strategy)
    now = time.time()
    cached = _PSI_CACHE.get(cache_key)
    if cached and cached[0] > now:
        return cached[1]

    data = await _async_fetch_with_retries(
        url=url,
        strategy=strategy,
        api_key=api_key_resolved,
    )

    if _should_cache(data):
        _PSI_CACHE[cache_key] = (now + cache_ttl, data)

    return data


# --------- Synchronous compatibility wrapper (if needed) ---------
def fetch_psi(
    url: str,
    strategy: str = "desktop",
    api_key: Optional[str] = None,
    cache_ttl: float = DEFAULT_CACHE_TTL,
) -> Optional[Dict[str, Any]]:
    """
    Sync wrapper for environments that cannot go async end-to-end.
    Runs the async function in a temporary event loop.
    Prefer async_fetch_psi in async code paths.
    """
    import asyncio
    return asyncio.run(async_fetch_psi(url=url, strategy=strategy, api_key=api_key, cache_ttl=cache_ttl))
