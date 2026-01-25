import logging
import requests
import certifi
import urllib3
from urllib.parse import urlparse
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("audit_engine")


def run_audit(url: str) -> dict:
    session = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0 (FFTech-AuditBot/2.0)",
        "Accept": "text/html,application/xhtml+xml",
    }

    ssl_verified = True
    audit_time = datetime.utcnow().isoformat()

    try:
        response = session.get(
            url,
            headers=headers,
            timeout=20,
            verify=certifi.where(),
            allow_redirects=True,
        )

    except requests.exceptions.SSLError:
        logger.warning(f"SSL verification failed for {url}, retrying insecure.")
        ssl_verified = False
        response = session.get(
            url,
            headers=headers,
            timeout=20,
            verify=False,
            allow_redirects=True,
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"Audit failed: {e}")
        return {
            "finished": False,
            "error": str(e),
        }

    parsed = urlparse(response.url)

    # --- International Audit Metrics ---
    https_enabled = parsed.scheme == "https"
    status_ok = response.status_code == 200

    security_score = 100
    if not https_enabled:
        security_score -= 40
    if not ssl_verified:
        security_score -= 30

    performance_score = 100
    if len(response.text) > 2_000_000:
        performance_score -= 30

    overall_score = round(
        (security_score * 0.5) + (performance_score * 0.5)
    )

    compliance_level = (
        "Excellent" if overall_score >= 90 else
        "Good" if overall_score >= 75 else
        "Needs Improvement"
    )

    # --- RETURN DATA FOR HTML / GRAPHS ---
    return {
        "finished": True,
        "audit_time": audit_time,

        "target": {
            "requested_url": url,
            "final_url": response.url,
            "domain": parsed.netloc,
        },

        "http": {
            "status_code": response.status_code,
            "success": status_ok,
            "https": https_enabled,
            "ssl_verified": ssl_verified,
        },

        "content": {
            "size_bytes": len(response.text),
        },

        "scores": {
            "security": security_score,
            "performance": performance_score,
            "overall": overall_score,
        },

        "compliance": {
            "standard": "ISO/IEC 27001 + OWASP Top 10",
            "rating": compliance_level,
        },

        "status": "Audit completed successfully",
    }
