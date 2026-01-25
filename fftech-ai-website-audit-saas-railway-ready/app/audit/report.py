# app/audit/record.py
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Dict, Set

def fetch_site_html(base_url: str, max_pages: int = 20) -> Dict[str, str]:
    """
    Fetch HTML content of a website, recursively crawling internal links.
    Returns: {url: html_content}
    """
    visited: Set[str] = set()
    to_visit: Set[str] = {base_url}
    html_docs: Dict[str, str] = {}

    headers = {"User-Agent": "Mozilla/5.0 (FFTech AI Auditor)"}

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop()
        if url in visited:
            continue
        try:
            r = requests.get(url, headers=headers, timeout=15, verify=False)
            html_docs[url] = r.text
            visited.add(url)

            # Parse internal links
            soup = BeautifulSoup(r.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                joined_url = urljoin(url, href)
                if urlparse(joined_url).netloc == urlparse(base_url).netloc:
                    if joined_url not in visited:
                        to_visit.add(joined_url)
        except Exception as e:
            print(f"[Fetch HTML] Failed to fetch {url}: {e}")

    return html_docs
