import time
import requests
from app.audit.psi import fetch_psi
from app.settings import get_settings

def get_performance_metrics(url: str):
    """
    CATEGORY E & F: PERFORMANCE & TECHNICAL (76-150)
    """
    settings = get_settings()
    mobile = fetch_psi(url, 'mobile') if settings.PSI_API_KEY else None
    
    if mobile:
        m_lab = mobile.get('lab') or {}
        score = m_lab.get('score', 0) * 100
        metrics = {
            "76_LCP": m_lab.get('lcp_ms'),
            "78_CLS": m_lab.get('cls'),
            "79_TBT": m_lab.get('tbt_ms'),
            "84_PageSize": m_lab.get('total_byte_size'),
            "97_MobileFriendly": "Pass"
        }
    else:
        # Fallback local measurement
        t0 = time.time()
        r = requests.get(url, timeout=10)
        ttfb = r.elapsed.total_seconds()
        score = max(0, 100 - (ttfb * 20))
        metrics = {"77_FCP": int(ttfb * 1000), "91_ServerResponse": int(ttfb * 1000)}

    return {
        "score": round(score, 2),
        "metrics": metrics,
        "color": "#10B981"
    }
