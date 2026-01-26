# fftech-ai-website-audit-saas-railway-ready/app/audit/record.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Dict, Set

def fetch_site_html(base_url: str, max_pages: int = 50) -> Dict[str, str]:
    """Fetch multiple same-host pages and return {url: html}."""
    visited: Set[str] = set()
    to_visit: Set[str] = {base_url}
    html_docs: Dict[str, str] = {}

    headers = {'User-Agent': 'Mozilla/5.0 (FFTech AI Auditor)'}

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop()
        if url in visited:
            continue
        try:
            r = requests.get(url, headers=headers, timeout=15, verify=False)
            html_docs[url] = r.text
            visited.add(url)

            soup = BeautifulSoup(r.text, 'lxml')
            for a in soup.find_all('a', href=True):
                href = a['href']
                joined_url = urljoin(url, href)
                if urlparse(joined_url).netloc == urlparse(base_url).netloc and joined_url not in visited:
                    to_visit.add(joined_url)
        except Exception:
            continue

    return html_docs
