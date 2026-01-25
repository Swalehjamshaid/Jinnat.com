import logging
import requests
import certifi
import urllib3
from urllib.parse import urlparse

# Disable warnings only if we have to fall back to insecure mode
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
            verify=certifi.where(), # Use the trusted bundle
            allow_redirects=True,
        )
    except requests.exceptions.SSLError:
        # 2. Fallback: If SSL fails, try once more without verification
        # This is crucial for an audit tool because you still want to 
        # analyze the site's content even if their SSL is misconfigured.
        logger.warning(f"SSL verification failed for {url}. Retrying without verification.")
        ssl_verified = False
        response = session.get(
            url,
            headers=headers,
            timeout=20,
            verify=False, # Ignore the chain error
            allow_redirects=True,
        )
    except requests.exceptions.Timeout:
        raise RuntimeError("The website took too long to respond.")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch URL: {e}")

    # 3. Process Result
    parsed = urlparse(response.url)
    
    return {
        "finished": True, # Changed to True since it worked
        "url": response.url,
        "domain": parsed.netloc,
        "http_status": response.status_code,
        "https": parsed.scheme == "https",
        "ssl_secure": ssl_verified, # Pass this back to your frontend!
        "content_length": len(response.text),
        "status": "Audit completed" if ssl_verified else "Audit completed with SSL warnings",
    }
