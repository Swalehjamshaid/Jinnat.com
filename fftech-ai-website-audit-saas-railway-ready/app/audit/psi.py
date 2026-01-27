import json
import time
import urllib.request
import urllib.parse
import ssl
from typing import Dict

def fetch_lighthouse(
    url: str,
    api_key: str,
    strategy: str = 'desktop',
    timeout: int = 25,
    retries: int = 1,
) -> Dict[str, int]:
    if not api_key:
        return {}

    encoded_url = urllib.parse.quote(url, safe='')
    endpoint = f'https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={encoded_url}&key={api_key}&strategy={strategy}'
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(endpoint, headers={'User-Agent': 'FFTechAuditor/2.0', 'Accept': 'application/json'})

    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
                if resp.getcode() != 200:
                    return {}
                raw = resp.read().decode('utf-8', errors='ignore')
                data = json.loads(raw)
                audits = data.get('lighthouseResult', {}).get('audits', {})
                lcp = audits.get('largest-contentful-paint', {}).get('numericValue', 0)
                fcp = audits.get('first-contentful-paint', {}).get('numericValue', 0)
                total_bytes = audits.get('total-byte-weight', {}).get('numericValue', 0)
                return {
                    'lcp_ms': int(lcp) if isinstance(lcp, (int, float)) else 0,
                    'fcp_ms': int(fcp) if isinstance(fcp, (int, float)) else 0,
                    'total_page_size_kb': int(total_bytes / 1024) if isinstance(total_bytes, (int, float)) else 0,
                }
        except Exception:
            if attempt < retries:
                time.sleep(2)
                continue
            return {}
    return {}
