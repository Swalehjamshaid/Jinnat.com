# app/audit/performance.py
import time
from .psi import fetch_lighthouse
from ..settings import get_settings
import asyncio
import requests
import urllib3

# Disable SSL warnings to keep logs clean
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

async def analyze_performance(url: str):
    """
    Measures website performance:
    - Tries Google PSI / Lighthouse first (if API key present)
    - Falls back to simple request-based timing
    - Returns LCP, FCP, total size, and server response time
    """
    settings = get_settings()

    # Step 1: Attempt Google PSI / Lighthouse asynchronously
    mobile_result, desktop_result = {}, {}
    if settings.PSI_API_KEY:
        try:
            mobile_result, desktop_result = await asyncio.gather(
                fetch_lighthouse(url, api_key=settings.PSI_API_KEY, strategy="mobile"),
                fetch_lighthouse(url, api_key=settings.PSI_API_KEY, strategy="desktop")
            )
        except Exception as e:
            print(f"[Performance] Lighthouse async fetch failed: {e}")

    # Use desktop metrics if available, else mobile, else fallback
    result = desktop_result or mobile_result
    if result:
        result['fallback_active'] = False
        return result

    # Step 2: Fallback with SSL bypass (for sites with certificate issues)
    t0 = time.time()
    try:
        r = requests.get(
            url,
            timeout=15,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (FFTech AI Auditor)"}
        )
        size = len(r.content)
        ttfb = r.elapsed.total_seconds()
    except Exception as e:
        print(f"[Performance Fallback] Error for {url}: {e}")
        size, ttfb = 0, 15

    total_time = time.time() - t0

    return {
        "lcp_ms": min(4000, int(total_time * 1000)),
        "fcp_ms": min(2500, int(ttfb * 1000)),
        "total_page_size_kb": int(size / 1024),
        "server_response_time_ms": int(ttfb * 1000),
        "fallback_active": True
    }
