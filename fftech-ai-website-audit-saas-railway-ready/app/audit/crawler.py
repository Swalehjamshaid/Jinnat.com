# app/audit/crawler.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, defaultdict
import time
import logging

logger = logging.getLogger("crawler_engine")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FFTechAuditor/1.0; +https://fftech.ai)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

class CrawlResult:
    def __init__(self):
        self.pages = {}  
        self.status_counts = defaultdict(int)
        self.internal_links = defaultdict(list)
        self.external_links = defaultdict(list)
        self.broken_internal = []  
        self.broken_external = []
        self.total_crawl_time = 0

def is_same_host(start_url: str, link: str) -> bool:
    try:
        return urlparse(start_url).netloc == urlparse(link).netloc
    except: return False

def crawl(start_url: str, max_pages: int = 15, timeout: int = 7) -> CrawlResult:
    """
    World-Class Speed Optimization:
    - Reduced max_pages (15 is enough for a quick health check).
    - Skip non-HTML files early (PDFs, Images, etc.).
    - Limited broken link validation to the first 10 links per page.
    """
    start_time = time.time()
    queue = deque([start_url])
    seen = set()
    result = CrawlResult()
    session = requests.Session()
    session.headers.update(HEADERS)

    # 1. Faster Crawl Loop
    while queue and len(seen) < max_pages:
        url = queue.popleft()
        if url in seen: continue
        seen.add(url)

        try:
            # stream=True allows us to check headers before downloading body
            r = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
            result.status_counts[r.status_code] += 1
            
            if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", "").lower():
                r.close() # Close connection without reading
                continue

            html = r.text
            result.pages[url] = html
            soup = BeautifulSoup(html, "html.parser")

            for tag in soup.find_all("a", href=True):
                href = tag.get("href").strip()
                # Optimized filter: skip common junk extensions
                if not href or any(href.endswith(ext) for ext in ['.pdf', '.jpg', '.png', '.zip', '.docx']):
                    continue
                if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                    continue
                
                abs_url = urljoin(url, href)
                if is_same_host(start_url, abs_url):
                    result.internal_links[url].append(abs_url)
                    if abs_url not in seen: queue.append(abs_url)
                else:
                    result.external_links[url].append(abs_url)

        except Exception as e:
            result.status_counts[0] += 1

    # 
    # 2. Optimized Link Validation (Check only unique internal links)
    checked_links = set()
    # Limit to 50 total link checks to keep it under 5 seconds
    total_checks = 0
    for src, links in result.internal_links.items():
        if total_checks > 50: break 
        for link in links[:10]: # Only check first 10 links per page
            if link in checked_links or link in result.pages: continue
            checked_links.add(link)
            total_checks += 1
            try:
                # HEAD is 10x faster than GET for link checking
                res = session.head(link, timeout=3, allow_redirects=True)
                if res.status_code >= 400:
                    result.broken_internal.append((src, link, res.status_code))
            except:
                result.broken_internal.append((src, link, 0))

    result.total_crawl_time = round(time.time() - start_time, 2)
    return result
