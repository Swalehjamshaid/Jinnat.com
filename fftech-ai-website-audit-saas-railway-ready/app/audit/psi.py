
# app/audit/psi.py
import os
import json
import asyncio
import httpx
from typing import Any, Dict, Optional

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

def _make_timeout(total_read_s: float) -> httpx.Timeout:
    # Tuned, sane defaults to avoid hangs
    return httpx.Timeout(connect=5.0, read=total_read_s, write=5.0, pool=5.0)

async def _async_fetch_with_retries(
    params: Dict[str, Any],
    retries: int = 2,
    backoff_base_s: float = 1.0,
    timeout_read_s: float = 15.0,
) -> Dict[str, Any]:
    """
    Fetch PSI JSON with retries & exponential backoff.
    """
    last_err: Optional[Exception] = None
    timeout = _make_timeout(timeout_read_s)

    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(PSI_ENDPOINT, params=params)
                resp.raise_for_status()
                return resp.json()
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.HTTPError) as e:
            last_err = e
            if attempt >= retries:
                raise
            # ✅ Correct async sleep
            await asyncio.sleep(backoff_base_s * (2 ** attempt))

    # Should not reach here
    if last_err:
        raise last_err
    raise RuntimeError("Unknown PSI fetch failure")

async def async_fetch_psi(
    url: str,
    strategy: str = "mobile",
    api_key: Optional[str] = None,
    timeout_read_s: float = 15.0,
    retries: int = 2,
) -> Dict[str, Any]:
    """
    Async PSI call. Use this in your async pipeline (recommended).
    """
    params: Dict[str, Any] = {
        "url": url,
        "strategy": strategy,
        # OPTIONAL: add categories if you want fuller payload
        # "category": ["performance", "seo", "accessibility", "best-practices"]
    }
    if api_key:
        params["key"] = api_key

    return await _async_fetch_with_retries(
        params=params,
        retries=retries,
        backoff_base_s=1.0,
        timeout_read_s=timeout_read_s,
    )

def fetch_psi(
    url: str,
    strategy: str = "mobile",
    api_key: Optional[str] = None,
    timeout_read_s: float = 15.0,
    retries: int = 2,
) -> Dict[str, Any]:
    """
    Synchronous wrapper for environments *without* an event loop.
    Do NOT call this from inside an async function or a running loop.
    Prefer async_fetch_psi in the audit pipeline.
    """
    return asyncio.run(
        async_fetch_psi(
            url=url,
            strategy=strategy,
            api_key=api_key,
            timeout_read_s=timeout_read_s,
            retries=retries,
        )
    )
