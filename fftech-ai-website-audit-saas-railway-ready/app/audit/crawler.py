# app/audit/crawler.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, defaultdict
import time

# Custom User-Agent to identify your bot to webmasters
HEADERS = {"User-Agent": "FFTechAuditor/1.0 (+https://fftech.ai)"}

class CrawlResult:
    def __init__(self):
        self.pages = {}  # URL: HTML content
        self.status_counts = defaultdict(int) # HTTP status distribution
        self.internal_links = defaultdict(list)
        self.external_links = defaultdict(list)
        self.broken_internal = [] # (source, target, status)
        self.broken_external = []
        self.total_crawl_time = 0

def is_same_host(start_url: str, link: str) -> bool:
    """Ensures we stay on the user's domain during the crawl."""
    return urlparse(start_url).netloc == urlparse(link).netloc

def crawl(start_url: str, max_pages: int = 50, timeout: int = 10) -> 'CrawlResult':
    """
    Performs a BFS crawl of the start_url up to max_pages.
    """
    start_time = time.time()
    q = deque([start_url])
    seen = set()
    result = CrawlResult()
    
    # 1. Main Discovery Loop
    while q and len(seen) < max_pages:
        url = q.popleft()
        if url in seen:
            continue
        seen.add(url)
        
        try:
            # allow_redirects=True ensures we find the final destination
            r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            result.status_counts[r.status_code] += 1
            
            # Only parse HTML pages
            if 'text/html' in r.headers.get('Content-Type', ''):
                soup = BeautifulSoup(r.text, 'html.parser')
                result.pages[url] = r.text
                
                for a in soup.find_all('a', href=True):
                    href = urljoin(url, a['href'])
                    
                    # Ignore non-web links
                    if href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                        continue
                        
                    if is_same_host(start_url, href):
                        result.internal_links[url].append(href)
                        if href not in seen:
                            q.append(href)
                    else:
                        result.external_links[url].append(href)
                        
        except requests.RequestException:
            result.status_counts[0] += 1

    # 2. Link Validation (HEAD requests)
    # Validating internal links helps grader.py calculate penalties
    checked_links = set()
    for src, links in result.internal_links.items():
        for l in links:
            if l in checked_links: continue
            checked_links.add(l)
            try:
                # Use HEAD instead of GET to save bandwidth
                rr = requests.head(l, headers=HEADERS, timeout=5, allow_redirects=True)
                if rr.status_code >= 400:
                    result.broken_internal.append((src, l, rr.status_code))
            except Exception:
                result.broken_internal.append((src, l, 0))

    # Limiting external checks to prevent getting blocked/throttled
    external_checked = set()
    for src, links in result.external_links.items():
        for l in links[:20]: # Only check first 20 external links for speed
            if l in external_checked: continue
            external_checked.add(l)
            try:
                rr = requests.head(l, headers=HEADERS, timeout=5, allow_redirects=True)
                if rr.status_code >= 400:
                    result.broken_external.append((src, l, rr.status_code))
            except Exception:
                result.broken_external.append((src, l, 0))

    result.total_crawl_time = round(time.time() - start_time, 2)
    return result
