# app/audit/crawler.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, defaultdict

HEADERS = {"User-Agent": "FFTechAuditor/1.0 (+https://fftech.ai)"}

class CrawlResult:
    def __init__(self):
        self.pages = {}
        self.status_counts = defaultdict(int)
        self.internal_links = defaultdict(list)
        self.external_links = defaultdict(list)
        self.broken_internal = []
        self.broken_external = []

def is_same_host(start_url: str, link: str) -> bool:
    return urlparse(start_url).netloc == urlparse(link).netloc

def crawl(start_url: str, max_pages: int = 50, timeout: int = 10) -> 'CrawlResult':
    q = deque([start_url])
    seen = set()
    result = CrawlResult()
    while q and len(seen) < max_pages:
        url = q.popleft()
        if url in seen:
            continue
        seen.add(url)
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            result.status_counts[r.status_code] += 1
            if 'text/html' in r.headers.get('Content-Type', ''):
                soup = BeautifulSoup(r.text, 'html.parser')
                result.pages[url] = r.text
                for a in soup.find_all('a', href=True):
                    href = urljoin(url, a['href'])
                    if href.startswith('mailto:') or href.startswith('tel:'):
                        continue
                    if is_same_host(start_url, href):
                        result.internal_links[url].append(href)
                        if href not in seen:
                            q.append(href)
                    else:
                        result.external_links[url].append(href)
        except requests.RequestException:
            result.status_counts[0] += 1

    # Broken link check (HEAD)
    checked = set()
    for src, links in result.internal_links.items():
        for l in links:
            if l in checked:
                continue
            checked.add(l)
            try:
                rr = requests.head(l, headers=HEADERS, timeout=5, allow_redirects=True)
                if rr.status_code >= 400:
                    result.broken_internal.append((src, l, rr.status_code))
            except Exception:
                result.broken_internal.append((src, l, 0))

    for src, links in result.external_links.items():
        for l in links[:50]:
            try:
                rr = requests.head(l, headers=HEADERS, timeout=5, allow_redirects=True)
                if rr.status_code >= 400:
                    result.broken_external.append((src, l, rr.status_code))
            except Exception:
                result.broken_external.append((src, l, 0))

    return result
