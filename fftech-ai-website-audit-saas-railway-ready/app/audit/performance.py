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
    Real-world website performance audit:
    1️⃣ Uses Google PageSpeed Insights if PSI_API_KEY exists.
    2️⃣ Falls back to actual HTTP request timing (LCP ~ load time, FCP ~ TTFB)
    3️⃣ Returns:
        - lcp_ms
        - fcp_ms
        - total_page_size_kb
        - server_response_time_ms
        - fallback_active
    """

    settings = get_settings()

    # Step 1: Try Google PSI / Lighthouse (async)
    desktop_result, mobile_result = {}, {}
    if settings.PSI_API_KEY:
        try:
            desktop_result, mobile_result = await asyncio.gather(
                fetch_lighthouse(url, api_key=settings.PSI_API_KEY, strategy="desktop"),
                fetch_lighthouse(url, api_key=settings.PSI_API_KEY, strategy="mobile")
            )
        except Exception as e:
            print(f"[Performance] PSI/Lighthouse fetch failed: {e}")

    # Prefer desktop metrics if available
    if desktop_result:
        desktop_result["fallback_active"] = False
        return desktop_result
    if mobile_result:
        mobile_result["fallback_active"] = False
        return mobile_result

    # Step 2: Fallback to live request measurements
    t0 = time.time()
    size = 0
    ttfb = 0

    try:
        with requests.get(
            url,
            timeout=20,
            verify=False,
            stream=True,
            headers={"User-Agent": "Mozilla/5.0 (FFTech AI Auditor)"}
        ) as r:
            r.raise_for_status()
            ttfb = r.elapsed.total_seconds()
            # Count actual page size
            content = r.content
            size = len(content)

    except requests.exceptions.RequestException as e:
        print(f"[Performance Fallback] Request error for {url}: {e}")
        size, ttfb = 0, 15

    total_time = time.time() - t0

    return {
        "lcp_ms": max(100, min(10000, int(total_time * 1000))),        # LCP ~ full load
        "fcp_ms": max(50, min(5000, int(ttfb * 1000))),                # FCP ~ TTFB
        "total_page_size_kb": int(size / 1024),
        "server_response_time_ms": int(ttfb * 1000),
        "fallback_active": True
    }
