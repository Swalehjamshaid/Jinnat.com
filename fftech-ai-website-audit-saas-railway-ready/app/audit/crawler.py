# app/audit/crawler.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, defaultdict
import time

HEADERS = {
    "User-Agent": "FFTechAuditor/1.0 (+https://fftech.ai)",
    "Accept": "text/html,application/xhtml+xml"
}

class CrawlResult:
    def __init__(self):
        self.pages = {}  # URL: HTML content
        self.status_counts = defaultdict(int)
        self.internal_links = defaultdict(list)
        self.external_links = defaultdict(list)
        self.broken_internal = []  # (source, target, status)
        self.broken_external = []
        self.total_crawl_time = 0

def is_same_host(start_url: str, link: str) -> bool:
    """Stay on the same host"""
    try:
        return urlparse(start_url).netloc == urlparse(link).netloc
    except Exception:
        return False

def crawl(start_url: str, max_pages: int = 50, timeout: int = 10) -> CrawlResult:
    """BFS Crawl: real, reliable audit. INPUT/OUTPUT unchanged."""
    start_time = time.time()
    queue = deque([start_url])
    seen = set()
    result = CrawlResult()

    session = requests.Session()
    session.headers.update(HEADERS)

    RETRIES = 2

    while queue and len(seen) < max_pages:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)

        for attempt in range(RETRIES):
            try:
                r = session.get(url, timeout=timeout, allow_redirects=True)
                result.status_counts[r.status_code] += 1
                if "text/html" not in r.headers.get("Content-Type", "").lower():
                    break
                html = r.text
                result.pages[url] = html
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup.find_all("a", href=True):
                    href = tag.get("href").strip()
                    if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
                        continue
                    absolute_url = urljoin(url, href)
                    if is_same_host(start_url, absolute_url):
                        result.internal_links[url].append(absolute_url)
                        if absolute_url not in seen:
                            queue.append(absolute_url)
                    else:
                        result.external_links[url].append(absolute_url)
                break  # success, break retry loop
            except requests.RequestException:
                if attempt == RETRIES - 1:
                    result.status_counts[0] += 1
            except Exception:
                if attempt == RETRIES - 1:
                    result.status_counts[0] += 1

    # Internal link validation
    checked_internal = set()
    for src, links in result.internal_links.items():
        for link in links:
            if link in checked_internal:
                continue
            checked_internal.add(link)
            try:
                rr = session.head(link, timeout=5, allow_redirects=True)
                if rr.status_code >= 400:
                    result.broken_internal.append((src, link, rr.status_code))
            except Exception:
                result.broken_internal.append((src, link, 0))

    # External link validation (first 20 per source)
    checked_external = set()
    for src, links in result.external_links.items():
        for link in links[:20]:
            if link in checked_external:
                continue
            checked_external.add(link)
            try:
                rr = session.head(link, timeout=5, allow_redirects=True)
                if rr.status_code >= 400:
                    result.broken_external.append((src, link, rr.status_code))
            except Exception:
                result.broken_external.append((src, link, 0))

    result.total_crawl_time = round(time.time() - start_time, 2)
    return result
