# app/audit/performance.py
import time
import asyncio
import requests
import urllib3
from typing import Dict, Any

from .psi import fetch_lighthouse
from ..settings import get_settings

# Disable SSL warnings to keep logs clean
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


async def analyze_performance(url: str) -> Dict[str, Any]:
    """
    Measures website performance:
    - Tries Google PSI / Lighthouse first (if API key present)
    - Falls back to simple request-based timing if PSI fails
    Returns a dictionary with:
        lcp_ms, fcp_ms, total_page_size_kb, server_response_time_ms, fallback_active
    """
    settings = get_settings()

    mobile_result: Dict[str, Any] = {}
    desktop_result: Dict[str, Any] = {}

    # 1️⃣ Attempt Google PSI / Lighthouse asynchronously
    if settings.PSI_API_KEY:
        try:
            mobile_result, desktop_result = await asyncio.gather(
                fetch_lighthouse(url, api_key=settings.PSI_API_KEY, strategy="mobile"),
                fetch_lighthouse(url, api_key=settings.PSI_API_KEY, strategy="desktop"),
            )
        except Exception as e:
            print(f"[Performance] Lighthouse async fetch failed: {e}")

    # Use desktop metrics first, else mobile
    result: Dict[str, Any] = desktop_result or mobile_result
    if result:
        result['fallback_active'] = False
        return result

    # 2️⃣ Fallback: measure response time & page size using requests
    t0 = time.time()
    try:
        r = requests.get(
            url,
            timeout=15,
            verify=False,  # SSL bypass
            headers={"User-Agent": "Mozilla/5.0 (FFTech AI Auditor)"}
        )
        size = len(r.content)
        ttfb = r.elapsed.total_seconds()  # Time to first byte
    except Exception as e:
        print(f"[Performance Fallback] Error for {url}: {e}")
        size, ttfb = 0, 15  # Default values if request fails

    total_time = time.time() - t0

    return {
        "lcp_ms": min(4000, int(total_time * 1000)),           # fallback LCP
        "fcp_ms": min(2500, int(ttfb * 1000)),                # fallback FCP
        "total_page_size_kb": int(size / 1024),               # page size in KB
        "server_response_time_ms": int(ttfb * 1000),          # TTFB in ms
        "fallback_active": True
    }
