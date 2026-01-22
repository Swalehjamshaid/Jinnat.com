import time
import requests
import urllib3
from urllib.parse import urlparse
from app.audit.psi import fetch_psi

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "FFTechAuditor/1.0 (+https://fftech.ai)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def get_performance_metrics(url: str):
    """
    Real performance metrics with PSI fallback
    """
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url.lstrip('/')

    metrics = {}
    start_time = time.time()

    try:
        # Try real PSI first (most accurate)
        psi = fetch_psi(url, 'mobile') or fetch_psi(url, 'desktop')

        if psi is not None:
            lab = psi.get('lab', {})
            metrics["LCP_ms"] = lab.get('lcp_ms', 'N/A')
            metrics["CLS"] = lab.get('cls', 'N/A')
            metrics["INP_ms"] = lab.get('inp_ms', 'N/A')
            metrics["TBT_ms"] = lab.get('tbt_ms', 'N/A')
            metrics["Speed_Index_ms"] = lab.get('speed_index_ms', 'N/A')
            metrics["TTI_ms"] = lab.get('tti_ms', 'N/A')

            # Realistic score from PSI (0-100 scale)
            score = psi.get('categories', {}).get('performance_score', 50)
            if score is None:
                score = 50  # fallback

        else:
            # Fallback to basic request timing (less accurate)
            response = requests.get(url, headers=HEADERS, timeout=(6, 20), allow_redirects=True, verify=False)
            ttfb = response.elapsed.total_seconds()
            full_time = time.time() - start_time

            metrics["TTFB_ms"] = int(ttfb * 1000)
            metrics["Total_Load_Time_ms"] = int(full_time * 1000)
            metrics["Page_Size_KB"] = round(len(response.content) / 1024, 2)
            metrics["HTTPS"] = urlparse(url).scheme == 'https'
            metrics["Redirects"] = len(response.history)

            # Very conservative fallback score (penalize unknown)
            score = 60 - (ttfb * 20) - (metrics["Page_Size_KB"] / 100)

        score = max(0, min(100, score))
        color = "#10B981" if score >= 80 else "#F59E0B" if score >= 50 else "#EF4444"

        return {
            "score": round(score, 2),
            "metrics": metrics,
            "color": color
        }

    except Exception as e:
        metrics["Error"] = str(e)[:100]
        return {"score": 30.0, "metrics": metrics, "color": "#EF4444"}
