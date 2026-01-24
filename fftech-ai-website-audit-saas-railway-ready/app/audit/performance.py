# app/audit/performance.py

import time
import requests
from .psi import fetch_psi
from ..settings import get_settings

def analyze_performance(url: str):
    """
    Analyzes website speed using Google PageSpeed Insights (PSI) if available,
    otherwise falls back to a basic request-based speed check.
    """
    settings = get_settings()
    
    # Attempt to get high-fidelity data from Google PSI
    mobile = fetch_psi(url, 'mobile') if settings.PSI_API_KEY else None
    desktop = fetch_psi(url, 'desktop') if settings.PSI_API_KEY else None

    def safe_get_metric(device_data, scope, metric_key):
        """Helper to safely navigate the PSI response structure."""
        if not device_data or scope not in device_data:
            return None
        return device_data[scope].get(metric_key)

    if mobile or desktop:
        # Priority logic: Mobile Field -> Mobile Lab -> Desktop Field -> Desktop Lab
        metrics = {
            'psi': {'mobile': mobile, 'desktop': desktop},
            'lcp_ms': (
                safe_get_metric(mobile, 'field', 'lcp_ms') or 
                safe_get_metric(mobile, 'lab', 'lcp_ms') or 
                safe_get_metric(desktop, 'field', 'lcp_ms') or 
                safe_get_metric(desktop, 'lab', 'lcp_ms')
            ),
            'fcp_ms': (
                safe_get_metric(mobile, 'lab', 'fcp_ms') or 
                safe_get_metric(desktop, 'lab', 'fcp_ms')
            ),
            'cls': (
                safe_get_metric(mobile, 'field', 'cls') or 
                safe_get_metric(mobile, 'lab', 'cls') or 
                safe_get_metric(desktop, 'field', 'cls') or 
                safe_get_metric(desktop, 'lab', 'cls')
            ),
            'tbt_ms': (
                safe_get_metric(mobile, 'lab', 'tbt_ms') or 
                safe_get_metric(desktop, 'lab', 'tbt_ms')
            ),
            'speed_index_ms': (
                safe_get_metric(mobile, 'lab', 'speed_index_ms') or 
                safe_get_metric(desktop, 'lab', 'speed_index_ms')
            ),
            'tti_ms': (
                safe_get_metric(mobile, 'lab', 'tti_ms') or 
                safe_get_metric(desktop, 'lab', 'tti_ms')
            ),
        }
        return metrics

    # --- Fallback Mode: Basic HTTP Speed Check ---
    # Used when PSI_API_KEY is not configured or fails
    t0 = time.time()
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "FFTechPerformanceChecker/1.0"})
        size = len(r.content)
        ttfb = r.elapsed.total_seconds() # Time To First Byte
    except Exception as e:
        print(f"Performance Fallback Error: {e}")
        size = 0
        ttfb = 15

    total_time = time.time() - t0
    
    # Estimate Core Web Vitals based on raw response times
    return {
        'lcp_ms': min(4000, int(total_time * 1000)),
        'fcp_ms': min(2500, int(ttfb * 1000)),
        'total_page_size_kb': int(size / 1024),
        'server_response_time_ms': int(ttfb * 1000),
        'fallback_active': True
    }
