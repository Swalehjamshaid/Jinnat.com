# app/audit/performance.py
import time
import requests
import urllib3
from typing import Dict, Any
from .psi import fetch_lighthouse           # assuming this is already synchronous
from ..settings import get_settings

# Disable SSL warnings to keep logs clean
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def analyze_performance(url: str) -> Dict[str, Any]:
    """
    Real-world website performance audit (synchronous version):
    1. Uses Google PageSpeed Insights if PSI_API_KEY exists.
    2. Falls back to actual HTTP request timing (LCP ~ load time, FCP ~ TTFB)
    3. Returns:
       - lcp_ms
       - fcp_ms
       - total_page_size_kb
       - server_response_time_ms
       - fallback_active
    """
    settings = get_settings()

    # Step 1: Try Google PSI / Lighthouse (sequential calls – no gather needed)
    desktop_result = {}
    mobile_result = {}

    if settings.PSI_API_KEY:
        try:
            # Call synchronously – one after the other
            desktop_result = fetch_lighthouse(
                url,
                api_key=settings.PSI_API_KEY,
                strategy="desktop"
            )
            mobile_result = fetch_lighthouse(
                url,
                api_key=settings.PSI_API_KEY,
                strategy="mobile"
            )
        except Exception as e:
            print(f"[Performance] PSI/Lighthouse fetch failed: {e}")

    # Prefer desktop metrics if available and non-empty
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
            headers={"User-Agent": "Mozilla/5.0 (compatible; FFTech AI Auditor/2.0)"}
        ) as r:
            r.raise_for_status()
            ttfb = r.elapsed.total_seconds() * 1000  # already in seconds → convert to ms

            # Count actual page size (read full content)
            content = r.content
            size = len(content)
    except requests.exceptions.RequestException as e:
        print(f"[Performance Fallback] Request error for {url}: {e}")
        size = 0
        ttfb = 15000  # default 15 seconds in ms

    total_time_ms = int((time.time() - t0) * 1000)

    return {
        "lcp_ms": max(100, min(10000, total_time_ms)),              # LCP ≈ full load time
        "fcp_ms": max(50, min(5000, int(ttfb))),                    # FCP ≈ TTFB
        "total_page_size_kb": int(size / 1024),
        "server_response_time_ms": int(ttfb),
        "fallback_active": True
    }
