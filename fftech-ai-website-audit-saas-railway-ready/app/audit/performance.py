# app/audit/performance.py
import time
import requests
from typing import Dict

def analyze_performance(url: str) -> Dict[str, int]:
    """
    Measures website performance using pure Python:
    - Server response time (TTFB)
    - Full page load time
    - Total page size
    """
    headers = {"User-Agent": "Mozilla/5.0 (FFTech AI Auditor)"}
    t0 = time.time()
    try:
        r = requests.get(url, headers=headers, timeout=15, verify=False)
        size = len(r.content)
        ttfb = r.elapsed.total_seconds()
    except Exception as e:
        print(f"[Performance] Error fetching {url}: {e}")
        size, ttfb = 0, 15

    total_time = time.time() - t0

    return {
        "lcp_ms": min(4000, int(total_time * 1000)),
        "fcp_ms": min(2500, int(ttfb * 1000)),
        "total_page_size_kb": int(size / 1024),
        "server_response_time_ms": int(ttfb * 1000)
    }
