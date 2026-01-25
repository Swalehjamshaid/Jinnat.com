# app/audit/performance.py
import time
import requests
import urllib3
from .psi import fetch_lighthouse
from ..settings import get_settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

async def analyze_performance(url: str):
    """
    Async website performance measurement.
    Uses Google PSI if API key is present, else falls back to simple timing.
    """
    settings = get_settings()
    
    mobile_result = None
    desktop_result = None

    # Await PSI / Lighthouse calls
    if settings.PSI_API_KEY:
        mobile_result = await fetch_lighthouse(url, api_key=settings.PSI_API_KEY, strategy="mobile")
        desktop_result = await fetch_lighthouse(url, api_key=settings.PSI_API_KEY, strategy="desktop")

    if mobile_result or desktop_result:
        result = desktop_result or mobile_result
        result['fallback_active'] = False
        return result

    # Fallback: request-based measurement
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
        print(f"Performance fallback error for {url}: {e}")
        size, ttfb = 0, 15

    total_time = time.time() - t0
    return {
        'lcp_ms': min(4000, int(total_time * 1000)),
        'fcp_ms': min(2500, int(ttfb * 1000)),
        'total_page_size_kb': int(size / 1024),
        'server_response_time_ms': int(ttfb * 1000),
        'fallback_active': True
    }
