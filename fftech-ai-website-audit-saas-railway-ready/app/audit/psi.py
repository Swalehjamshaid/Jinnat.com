# app/audit/psi.py
import json
import time
import urllib.request
import urllib.parse
import urllib.error
import ssl
from typing import Dict

def fetch_lighthouse(
    url: str,
    api_key: str,
    strategy: str = "desktop",
    timeout: int = 25,
    retries: int = 1
) -> Dict[str, int]:
    """
    Fetch Google PageSpeed Insights (Lighthouse) data using only standard library.
    
    Returns dict with:
      - lcp_ms: Largest Contentful Paint (ms)
      - fcp_ms: First Contentful Paint (ms)
      - total_page_size_kb: Total byte weight / 1024
    
    Returns empty dict {} on any failure (no API key, network error, invalid response, etc.)
    """
    if not api_key:
        return {}

    # Build safe, encoded URL
    encoded_url = urllib.parse.quote(url, safe='')
    endpoint = (
        f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        f"?url={encoded_url}"
        f"&key={api_key}"
        f"&strategy={strategy}"
    )

    # Create SSL context that allows modern TLS but doesn't verify hostname/cert by default
    # (many production setups need this due to cert issues; adjust if you have strict policy)
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        endpoint,
        headers={
            'User-Agent': 'FFTechAuditor/2.0 (Python stdlib; contact: your@email.com)',
            'Accept': 'application/json'
        }
    )

    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
                if response.getcode() != 200:
                    try:
                        error_text = response.read().decode('utf-8', errors='ignore')
                    except:
                        error_text = ""
                    print(f"[PSI] HTTP {response.getcode()} for {url} ({strategy}): {error_text}")
                    return {}

                raw = response.read().decode('utf-8', errors='ignore')
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError as je:
                    print(f"[PSI] JSON decode error for {url} ({strategy}): {je}")
                    return {}

                audits = data.get("lighthouseResult", {}).get("audits", {})

                # Safe extraction with defaults
                lcp = audits.get("largest-contentful-paint", {}).get("numericValue", 0)
                fcp = audits.get("first-contentful-paint", {}).get("numericValue", 0)
                total_bytes = audits.get("total-byte-weight", {}).get("numericValue", 0)

                return {
                    "lcp_ms": int(lcp) if isinstance(lcp, (int, float)) else 0,
                    "fcp_ms": int(fcp) if isinstance(fcp, (int, float)) else 0,
                    "total_page_size_kb": int(total_bytes / 1024) if isinstance(total_bytes, (int, float)) else 0,
                }

        except urllib.error.HTTPError as http_err:
            try:
                error_body = http_err.read().decode('utf-8', errors='ignore')
            except:
                error_body = ""
            print(f"[PSI] HTTP error {http_err.code} for {url} ({strategy}): {http_err.reason} - {error_body}")
            return {}

        except urllib.error.URLError as url_err:
            print(f"[PSI] URL error for {url} ({strategy}): {url_err.reason}")
            if attempt < retries:
                time.sleep(2)  # brief backoff before retry
                continue
            return {}

        except ssl.SSLError as ssl_err:
            print(f"[PSI] SSL error for {url} ({strategy}): {ssl_err}")
            return {}

        except Exception as e:
            print(f"[PSI] Unexpected error for {url} ({strategy}): {type(e).__name__}: {e}")
            if attempt < retries:
                time.sleep(2)
                continue
            return {}

    return {}  # all retries failed
