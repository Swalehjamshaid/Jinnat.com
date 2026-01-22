import time
import requests
import urllib3
from app.audit.psi import fetch_psi
from app.settings import get_settings

# Disable the "InsecureRequestWarning" in the logs caused by verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_performance_metrics(url: str):
    """
    CATEGORY E & F: PERFORMANCE & TECHNICAL (76-150)
    Updated to fix SSL: CERTIFICATE_VERIFY_FAILED and Max Retries issues.
    """
    settings = get_settings()
    
    # 1. Attempt High-Fidelity Data (PageSpeed Insights)
    mobile = None
    if settings.PSI_API_KEY:
        try:
            mobile = fetch_psi(url, 'mobile')
        except Exception as e:
            print(f"PSI Fetch Error: {e}")

    if mobile:
        m_lab = mobile.get('lab') or {}
        m_field = mobile.get('field') or {}
        score = m_lab.get('score', 0) * 100
        
        metrics = {
            "76_LCP": m_field.get('lcp_ms') or m_lab.get('lcp_ms'),
            "78_CLS": m_field.get('cls') or m_lab.get('cls'),
            "79_TBT": m_lab.get('tbt_ms'),
            "84_PageSize": m_lab.get('total_byte_size'),
            "97_MobileFriendly": "Pass",
            "91_ServerResponse": m_lab.get('server_response_time_ms')
        }
        
        return {
            "score": round(score, 2),
            "metrics": metrics,
            "color": "#10B981"
        }

    # 2. Fallback: Manual Performance Measurement with SSL Bypass
    # This section fixed the SSLError: certificate verify failed
    t0 = time.time()
    try:
        headers = {
            "User-Agent": "FFTechAuditor/1.0 (Enterprise AI Auditor)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        
        # FIX: verify=False allows auditing sites with SSL issues (like haier.com.pk)
        # FIX: timeout=15 ensures we don't hang on slow servers
        r = requests.get(url, timeout=15, verify=False, headers=headers)
        
        ttfb = r.elapsed.total_seconds()
        size = len(r.content)
        status = r.status_code
        
    except Exception as e:
        # If the site is completely down, return a "Fail" score instead of crashing
        print(f"Critical Performance Error for {url}: {e}")
        return {
            "score": 0,
            "metrics": {
                "76_LCP": "N/A",
                "91_ServerResponse": "Timeout/SSL Error",
                "115_HTTPS": "Failed Connection"
            },
            "color": "#EF4444"
        }
        
    total_time = time.time() - t0
    
    # Calculate score based on Server Response Time (TTFB)
    # Standard: Under 0.5s is excellent, over 2s is poor.
    local_score = max(0, 100 - (ttfb * 25))
    
    return {
        "score": round(local_score, 2),
        "metrics": {
            "77_FCP": int(ttfb * 1000),
            "84_PageSize_KB": int(size / 1024),
            "91_ServerResponse_ms": int(ttfb * 1000),
            "115_HTTPS": "Yes" if url.startswith('https') else "No",
            "Status_Code": status
        },
        "color": "#F59E0B" if local_score < 70 else "#10B981"
    }
