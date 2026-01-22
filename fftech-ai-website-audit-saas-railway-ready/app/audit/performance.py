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


# -----------------------------
# Internal helpers (NON-BREAKING)
# -----------------------------

def _grade_from_score(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _cwv_pass_fail(lcp, cls, inp):
    """
    Google CWV thresholds
    """
    try:
        lcp_ok = lcp <= 2500
        cls_ok = cls <= 0.1
        inp_ok = inp <= 200
        return "PASS" if all([lcp_ok, cls_ok, inp_ok]) else "FAIL"
    except Exception:
        return "UNKNOWN"


def _detect_cdn(headers: dict) -> bool:
    cdn_headers = [
        "cf-ray", "cf-cache-status",
        "x-cache", "x-served-by",
        "akamai", "fastly", "cloudflare"
    ]
    return any(h.lower() in " ".join(headers.keys()).lower() for h in cdn_headers)


# -----------------------------
# Main public API (UNCHANGED)
# -----------------------------

def get_performance_metrics(url: str):
    """
    Real performance metrics with PSI fallback
    (Extended without breaking output)
    """
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url.lstrip('/')

    metrics = {}
    start_time = time.time()

    try:
        # ===============================
        # 1. Try PageSpeed Insights (best)
        # ===============================
        psi = fetch_psi(url, 'mobile') or fetch_psi(url, 'desktop')

        if psi is not None:
            lab = psi.get('lab', {})

            metrics["LCP_ms"] = lab.get('lcp_ms', 'N/A')
            metrics["CLS"] = lab.get('cls', 'N/A')
            metrics["INP_ms"] = lab.get('inp_ms', 'N/A')
            metrics["TBT_ms"] = lab.get('tbt_ms', 'N/A')
            metrics["Speed_Index_ms"] = lab.get('speed_index_ms', 'N/A')
            metrics["TTI_ms"] = lab.get('tti_ms', 'N/A')

            score = psi.get('categories', {}).get('performance_score', 50) or 50

            # CWV evaluation
            metrics["CWV_Status"] = _cwv_pass_fail(
                metrics["LCP_ms"],
                metrics["CLS"],
                metrics["INP_ms"]
            )

            metrics["Performance_Source"] = "PSI"

        # ===============================
        # 2. Fallback: Real request timing
        # ===============================
        else:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=(6, 20),
                allow_redirects=True,
                verify=False
            )

            ttfb = response.elapsed.total_seconds()
            full_time = time.time() - start_time

            metrics["TTFB_ms"] = int(ttfb * 1000)
            metrics["Total_Load_Time_ms"] = int(full_time * 1000)
            metrics["Page_Size_KB"] = round(len(response.content) / 1024, 2)
            metrics["HTTPS"] = urlparse(url).scheme == 'https'
            metrics["Redirects"] = len(response.history)
            metrics["CWV_Status"] = "UNKNOWN"
            metrics["Performance_Source"] = "HTTP_Fallback"

            # Conservative scoring
            score = 60 - (ttfb * 20) - (metrics["Page_Size_KB"] / 100)

        # ===============================
        # 3. Diagnostics & Insights
        # ===============================
        score = max(0, min(100, score))
        grade = _grade_from_score(score)

        metrics["Performance_Grade"] = grade

        # Server diagnosis
        if metrics.get("TTFB_ms", 0) > 800:
            metrics["Server_Diagnosis"] = "Slow backend response (optimize hosting / DB)"
        else:
            metrics["Server_Diagnosis"] = "Healthy server response"

        # CDN & caching
        try:
            head = requests.head(url, headers=HEADERS, timeout=6, allow_redirects=True, verify=False)
            metrics["CDN_Detected"] = _detect_cdn(head.headers)
            metrics["Caching_Headers"] = {
                "Cache-Control": head.headers.get("Cache-Control"),
                "Expires": head.headers.get("Expires"),
                "ETag": head.headers.get("ETag"),
            }
        except Exception:
            metrics["CDN_Detected"] = False

        # Opportunities
        opportunities = []

        if metrics.get("CWV_Status") == "FAIL":
            opportunities.append("Improve Core Web Vitals to meet Google ranking thresholds.")

        if metrics.get("TTFB_ms", 0) > 800:
            opportunities.append("Reduce server response time (TTFB).")

        if not metrics.get("CDN_Detected"):
            opportunities.append("Use a CDN to improve global performance.")

        metrics["Performance_Opportunities"] = opportunities

        # Color (unchanged logic)
        color = "#10B981" if score >= 80 else "#F59E0B" if score >= 50 else "#EF4444"

        return {
            "score": round(score, 2),
            "metrics": metrics,
            "color": color
        }

    except Exception as e:
        metrics["Error"] = str(e)[:100]
        return {
            "score": 30.0,
            "metrics": metrics,
            "color": "#EF4444"
        }
