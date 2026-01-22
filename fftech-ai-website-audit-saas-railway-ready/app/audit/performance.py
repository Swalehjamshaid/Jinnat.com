import time
import requests
import urllib3
from urllib.parse import urlparse

# Suppress InsecureRequestWarning (common for international sites)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "FFTechAuditor/1.0 (+https://fftech.ai)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def get_performance_metrics(url: str):
    """
    Measures basic performance metrics for the given URL.
    Returns score (0-100), metrics dict, and color.
    """
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url.lstrip('/')

    metrics = {}
    start_time = time.time()

    try:
        # First request - measure TTFB & redirects
        session = requests.Session()
        session.verify = False  # for sites with problematic certs

        response = session.get(
            url,
            headers=HEADERS,
            timeout=(5, 15),  # connect timeout 5s, read timeout 15s
            allow_redirects=True
        )

        ttfb = response.elapsed.total_seconds()  # Time To First Byte
        full_load_time = time.time() - start_time

        # Basic metrics
        metrics["77_FCP_ms"] = int(ttfb * 1000)                     # First Contentful Paint approximation
        metrics["91_Server_Response_ms"] = int(ttfb * 1000)
        metrics["92_Total_Load_Time_ms"] = int(full_load_time * 1000)
        metrics["115_HTTPS"] = urlparse(url).scheme == 'https'
        metrics["84_Page_Size_KB"] = round(len(response.content) / 1024, 2)
        metrics["85_Number_of_Requests"] = 1 + len(response.history)  # + redirects
        metrics["86_Redirects"] = len(response.history)

        # Penalties calculation (more balanced)
        penalties = 0

        # TTFB penalties (Google recommends < 800ms for good)
        if ttfb > 2.0:
            penalties += (ttfb - 0.8) * 20
        elif ttfb > 1.2:
            penalties += (ttfb - 0.8) * 10

        # Page size penalties (ideal < 1500 KB)
        page_size_kb = metrics["84_Page_Size_KB"]
        if page_size_kb > 3000:
            penalties += (page_size_kb - 1500) / 100 * 15
        elif page_size_kb > 2000:
            penalties += (page_size_kb - 1500) / 100 * 8

        # HTTPS penalty
        if not metrics["115_HTTPS"]:
            penalties += 30

        # Redirect chain penalty
        if metrics["86_Redirects"] > 2:
            penalties += (metrics["86_Redirects"] - 1) * 8

        # Final score
        score = max(0, 100 - round(penalties, 1))
        score = min(100, score)

        color = "#10B981" if score >= 70 else "#F59E0B" if score >= 40 else "#EF4444"

        return {
            "score": round(score, 2),
            "metrics": metrics,
            "color": color
        }

    except requests.Timeout:
        metrics["91_Error"] = "Request Timeout"
        metrics["92_Total_Load_Time_ms"] = 9999
        return {"score": 10.0, "metrics": metrics, "color": "#EF4444"}

    except requests.ConnectionError:
        metrics["91_Error"] = "Connection Failed"
        return {"score": 5.0, "metrics": metrics, "color": "#EF4444"}

    except requests.RequestException as e:
        metrics["91_Error"] = f"Request Error: {str(e)[:60]}"
        return {"score": 0.0, "metrics": metrics, "color": "#EF4444"}

    except Exception as e:
        metrics["91_Error"] = f"Unexpected: {str(e)[:60]}"
        return {"score": 0.0, "metrics": metrics, "color": "#EF4444"}
