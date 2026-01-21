
import time, requests
from .psi import fetch_psi
from ..settings import get_settings

def analyze_performance(url: str):
    settings = get_settings()
    mobile = fetch_psi(url, 'mobile') if settings.PSI_API_KEY else None
    desktop = fetch_psi(url, 'desktop') if settings.PSI_API_KEY else None
    if mobile or desktop:
        def pick(dic, key):
            return dic and dic.get(key)
        return {
            'psi': {'mobile': mobile, 'desktop': desktop},
            'lcp_ms': (pick(mobile,'field') or {}).get('lcp_ms') or (pick(mobile,'lab') or {}).get('lcp_ms') or (pick(desktop,'field') or {}).get('lcp_ms') or (pick(desktop,'lab') or {}).get('lcp_ms'),
            'fcp_ms': (pick(mobile,'lab') or {}).get('fcp_ms') or (pick(desktop,'lab') or {}).get('fcp_ms'),
            'cls': (pick(mobile,'field') or {}).get('cls') or (pick(mobile,'lab') or {}).get('cls') or (pick(desktop,'field') or {}).get('cls') or (pick(desktop,'lab') or {}).get('cls'),
            'tbt_ms': (pick(mobile,'lab') or {}).get('tbt_ms') or (pick(desktop,'lab') or {}).get('tbt_ms'),
            'speed_index_ms': (pick(mobile,'lab') or {}).get('speed_index_ms') or (pick(desktop,'lab') or {}).get('speed_index_ms'),
            'tti_ms': (pick(mobile,'lab') or {}).get('tti_ms') or (pick(desktop,'lab') or {}).get('tti_ms'),
        }
    t0 = time.time()
    try:
        r = requests.get(url, timeout=15)
        size = len(r.content)
        ttfb = r.elapsed.total_seconds()
    except Exception:
        size = 0
        ttfb = 15
    total = time.time()-t0
    lcp = min(4000, int(total*1000))
    fcp = min(2500, int(ttfb*1000))
    return {'lcp_ms': lcp, 'fcp_ms': fcp, 'total_page_size_kb': int(size/1024), 'requests_per_page': None, 'server_response_time_ms': int(ttfb*1000)}
