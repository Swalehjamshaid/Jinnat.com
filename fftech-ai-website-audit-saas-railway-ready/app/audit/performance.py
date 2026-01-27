# app/audit/performance.py
import time
import httpx
from typing import Dict

def fetch_timing(url: str, timeout: float = 10.0) -> Dict[str, int]:
    """
    Crude network timing (TTFB-like): time to first response using GET with redirects.
    Returns lcp_ms-like number for illustrative purposes.
    """
    start = time.time()
    try:
        with httpx.Client(timeout=timeout, verify=False, follow_redirects=True) as client:
            client.get(url)
        elapsed_ms = int((time.time() - start) * 1000)
    except Exception:
        elapsed_ms = 9999

    # Make a pseudo-performance score from elapsed time
    speed_score = max(0, min(100, int(100 - (elapsed_ms / 100))))
    return {"lcp_ms": elapsed_ms, "speed_score": speed_score}
