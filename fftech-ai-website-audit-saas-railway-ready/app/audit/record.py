# app/audit/record.py
import urllib.request
import urllib.error
import urllib.parse
import ssl
from typing import Dict, Union


def fetch_site_html(url: str, timeout: int = 15) -> Dict[str, str]:
    """
    Fetch HTML content of a website using only Python standard library.
    Returns {url: html_string} or {url: ""} on failure.
    
    - Ignores SSL certificate verification (like the original) to avoid common issues
    - Uses a proper User-Agent
    - Handles basic redirects and timeouts
    """
    html_docs: Dict[str, str] = {}

    # Prepare request
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; FFTech AI Auditor/2.0; +https://yourdomain.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    # Disable SSL verification (matches original behavior)
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        # Build request
        req = urllib.request.Request(
            url,
            headers=headers,
            method="GET"
        )

        # Open connection
        with urllib.request.urlopen(
            req,
            timeout=timeout,
            context=context
        ) as response:

            # Follow redirects manually if needed (urllib does basic handling)
            final_url = response.geturl()
            code = response.getcode()

            if code != 200:
                print(f"Non-200 status for {final_url}: {code}")
                html_docs[url] = ""
                return html_docs

            # Read and decode
            raw_bytes = response.read()
            try:
                html = raw_bytes.decode("utf-8", errors="replace")
            except Exception:
                html = raw_bytes.decode("latin-1", errors="replace")

            html_docs[url] = html

    except urllib.error.HTTPError as e:
        print(f"HTTP error for {url}: {e.code} - {e.reason}")
        html_docs[url] = ""
    except urllib.error.URLError as e:
        print(f"URL error for {url}: {e.reason}")
        html_docs[url] = ""
    except ssl.SSLError as e:
        print(f"SSL error for {url}: {e}")
        html_docs[url] = ""
    except Exception as e:
        print(f"Unexpected error fetching {url}: {type(e).__name__}: {e}")
        html_docs[url] = ""

    return html_docs
