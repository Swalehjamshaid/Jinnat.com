import time
import requests
import urllib3
from urllib.parse import urlparse
from app.audit.psi import fetch_psi

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "FFTechAuditor/1.0 (+https://fftech.ai)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def get_performance_metrics(url: str):
    """
    Measures basic performance metrics for the given URL.
    Integrates real PSI data for accurate Core Web Vitals.
    Returns score (0-100), metrics dict, and color.
    """
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    metrics = {}
    start_time = time.time()

    try:
        # Get real PSI data
        psi_mobile = fetch_psi(url, 'mobile')
        psi_desktop = fetch_psi(url, 'desktop')
        psi = psi_mobile or psi_desktop or {}

        # Basic request for TTFB, size, etc.
        response = requests.get(url, headers=HEADERS, timeout=(6, 20), allow_redirects=True, verify=False)
        ttfb = response.elapsed.total_seconds()
        full_load_time = time.time() - start_time

        # Lab metrics from PSI (prefer mobile)
        lab = psi.get('lab', {})
        metrics["77_FCP_ms"] = lab.get('fcp_ms', int(ttfb * 1000))
        metrics["91_Server_Response_ms"] = int(ttfb * 1000)
        metrics["92_Total_Load_Time_ms"] = int(full_load_time * 1000)
        metrics["115_HTTPS"] = urlparse(url).scheme == 'https'
        metrics["84_Page_Size_KB"] = round(len(response.content) / 1024, 2)
        metrics["85_Number_of_Requests"] = 1 + len(response.history)
        metrics["86_Redirects"] = len(response.history)
        metrics["LCP_ms"] = lab.get('lcp_ms', 'N/A')
        metrics["CLS"] = lab.get('cls', 'N/A')
        metrics["TBT_ms"] = lab.get('tbt_ms', 'N/A')
        metrics["INP_ms"] = psi.get('field', {}).get('inp_ms', 'N/A')

        # Score calculation using PSI data
        penalties = 0
        lcp = lab.get('lcp_ms', 4000)
        if lcp > 2500:
            penalties += (lcp - 2500) / 20
        cls = lab.get('cls', 0.25)
        if cls > 0.1:
            penalties += cls * 300
        tbt = lab.get('tbt_ms', 500)
        if tbt > 200:
            penalties += (tbt - 200) / 5
        if not metrics["115_HTTPS"]:
            penalties += 25
        if metrics["86_Redirects"] > 1:
            penalties += metrics["86_Redirects"] * 8

        score = max(0, 100 - penalties)
        score = min(100, score)

        color = "#10B981" if score >= 75 else "#F59E0B" if score >= 50 else "#EF4444"

        return {
            "score": round(score, 2),
            "metrics": metrics,
            "color": color
        }

    except Exception as e:
        metrics["91_Error"] = str(e)[:100]
        return {"score": 20.0, "metrics": metrics, "color": "#EF4444"}
