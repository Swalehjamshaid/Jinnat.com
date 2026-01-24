# app/audit/crawler.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, defaultdict
import time
import logging

logger = logging.getLogger("crawler_engine")

# World-class User-Agent to prevent getting blocked
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FFTechAuditor/1.0; +https://fftech.ai)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
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
    except Exception:
        return False

def crawl(start_url: str, max_pages: int = 50, timeout: int = 10) -> CrawlResult:
    """
    Optimized BFS Crawler:
    - Robust error handling for modern JS-heavy sites.
    - Faster link validation.
    """
    start_time = time.time()
    queue = deque([start_url])
    seen = set()
    result = CrawlResult()

    # Using a session for connection pooling (much faster)
    session = requests.Session()
    session.headers.update(HEADERS)

    logger.info(f"🕸️ Starting crawl for: {start_url}")

    while queue and len(seen) < max_pages:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)

        try:
            # allow_redirects=True is vital for modern sites
            r = session.get(url, timeout=timeout, allow_redirects=True)
            result.status_counts[r.status_code] += 1
            
            if r.status_code != 200:
                continue

            if "text/html" not in r.headers.get("Content-Type", "").lower():
                continue

            html = r.text
            result.pages[url] = html
            soup = BeautifulSoup(html, "html.parser")

            for tag in soup.find_all("a", href=True):
                href = tag.get("href").strip()
                if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
                    continue
                
                absolute_url = urljoin(url, href)
                
                # Stay on the same domain for crawling, but record external for auditing
                if is_same_host(start_url, absolute_url):
                    result.internal_links[url].append(absolute_url)
                    if absolute_url not in seen:
                        queue.append(absolute_url)
                else:
                    result.external_links[url].append(absolute_url)

        except Exception as e:
            logger.warning(f"⚠️ Failed to crawl {url}: {e}")
            result.status_counts[0] += 1

    # ======================================
    # Fast Link Validation (Internal only)
    # To keep it world-class, we only check internal links to save time
    # ======================================
    checked_links = set()
    for src, links in result.internal_links.items():
        for link in links:
            if link in checked_links or link in result.pages:
                continue
            checked_links.add(link)
            try:
                # Use HEAD request instead of GET (saves 90% bandwidth)
                res = session.head(link, timeout=5, allow_redirects=True)
                if res.status_code >= 400:
                    result.broken_internal.append((src, link, res.status_code))
            except:
                result.broken_internal.append((src, link, 0))

    result.total_crawl_time = round(time.time() - start_time, 2)
    logger.info(f"✅ Crawl finished. Found {len(result.pages)} pages in {result.total_crawl_time}s")
    return result
