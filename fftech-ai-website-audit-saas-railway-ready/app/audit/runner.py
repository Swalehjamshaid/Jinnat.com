import logging
import requests
import certifi
import urllib3
from urllib.parse import urlparse

# This prevents console noise when you bypass SSL for a specific site
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("audit_engine")

def run_audit(url: str) -> dict:
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; FFTech-AuditBot/2.0; +https://audit.fftech)",
        "Accept": "text/html,application/xhtml+xml",
    }

    ssl_verified = True
    
    try:
        # 1. Attempt Secure Request
        response = session.get(
            url,
            headers=headers,
            timeout=20,
            verify=certifi.where(), 
            allow_redirects=True,
        )
    except requests.exceptions.SSLError:
        # 2. Fallback: Catch SSL error and retry without verification
        logger.warning(f"SSL verification failed for {url}. Retrying without verification.")
        ssl_verified = False
        response = session.get(
            url,
            headers=headers,
            timeout=20,
            verify=False, # This allows the audit to proceed
            allow_redirects=True,
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Audit failed: {e}")
        raise RuntimeError(f"Failed to fetch URL: {e}")

    parsed = urlparse(response.url)
    
    # 3. Return the result dictionary so the UI can update
    return {
        "finished": True,
        "url": response.url,
        "domain": parsed.netloc,
        "http_status": response.status_code,
        "https": parsed.scheme == "https",
        "ssl_secure": ssl_verified, 
        "content_length": len(response.text),
        "status": "Audit completed successfully",
    }
