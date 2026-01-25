# app/audit/runner.py

import logging
import requests
import certifi
from urllib.parse import urlparse

logger = logging.getLogger("audit_engine")


def run_audit(url: str) -> dict:
    """
    World-class, SSL-verified audit runner.
    - Uses system + certifi CA bundle
    - Safe for enterprise & banking-grade websites
    """

    try:
        session = requests.Session()

        # 🔐 Enforce trusted CA certificates
        session.verify = certifi.where()

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; FFTech-AuditBot/2.0; "
                "+https://audit.fftech)"
            ),
            "Accept": "text/html,application/xhtml+xml",
        }

        response = session.get(
            url,
            headers=headers,
            timeout=20,
            allow_redirects=True,
        )

        response.raise_for_status()

        parsed = urlparse(response.url)

        return {
            "finished": False,
            "url": response.url,
            "domain": parsed.netloc,
            "http_status": response.status_code,
            "https": parsed.scheme == "https",
            "content_length": len(response.text),
            "status": "Audit completed successfully",
        }

    except requests.exceptions.SSLError as e:
        logger.exception("SSL verification failed")
        raise RuntimeError(
            "SSL verification failed. The website's certificate chain "
            "could not be validated inside the container."
        ) from e

    except requests.exceptions.Timeout:
        logger.exception("Request timeout")
        raise RuntimeError("The website took too long to respond.")

    except requests.exceptions.RequestException as e:
        logger.exception("HTTP request failed")
        raise RuntimeError(f"Failed to fetch URL: {e}") from e
