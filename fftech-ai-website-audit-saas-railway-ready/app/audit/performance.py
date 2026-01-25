import time
import requests
import urllib3
from .psi import fetch_lighthouse
from ..settings import get_settings

# Disable SSL warnings to keep logs clean
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def analyze_performance(url: str):
    """
    Measures website performance:
    - Tries Google PSI / Lighthouse first (if API key present)
    - Falls back to simple request-based timing
    - Returns LCP, FCP, total size, and server response time
    """
    settings = get_settings()
    
    # Step 1: Attempt Google PSI / Lighthouse
    mobile_result = fetch_lighthouse(url, api_key=settings.PSI_API_KEY) if settings.PSI_API_KEY else None
    desktop_result = fetch_lighthouse(url, api_key=settings.PSI_API_KEY) if settings.PSI_API_KEY else None

    if mobile_result or desktop_result:
        # For simplicity, prioritize desktop metrics if available
        result = desktop_result or mobile_result
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
