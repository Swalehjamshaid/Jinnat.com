# app/audit/crawler.py
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

HEADERS = {"User-Agent": "FFTech-AuditBot/4.0"}

class CrawlResult:
    def __init__(self):
        self.visited = set()
        self.pages = []
        self.crawled_count = 0
        self.broken_internal = []
        self.broken_external = []
        self.unique_internal = 0
        self.unique_external = 0
        self.total_crawl_time = 0

def check_link(link):
    """Return True if link is broken"""
    try:
        r = requests.head(link, timeout=5, allow_redirects=True)
        return link, r.status_code >= 400
    except:
        return link, True

def crawl(start_url, max_pages=20, delay=0.1):
    """
    Crawl a website for internal/external links.
    Optimized to finish fast using limited pages.
    """
    start_time = time.time()
    domain = urlparse(start_url).netloc
    queue = deque([start_url])
    result = CrawlResult()
    all_internal_links, all_external_links = set(), set()

    while queue and len(result.visited) < max_pages:
        url = queue.popleft()
        if url in result.visited:
            continue
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
        except:
            continue
        result.visited.add(url)
        result.pages.append({"url": url, "soup": soup})
        result.crawled_count += 1

        internal_links, external_links = set(), set()
        for a in soup.select("a[href]"):
            link = urljoin(url, a["href"].split("#")[0])
            parsed = urlparse(link)
            if parsed.netloc == domain:
                internal_links.add(link)
                all_internal_links.add(link)
            else:
                external_links.add(link)
                all_external_links.add(link)

        for link in internal_links:
            if link not in result.visited and len(result.visited) + len(queue) < max_pages:
                queue.append(link)
        if delay:
            time.sleep(delay)

    # Check broken links in parallel (fast)
    def check_links_parallel(links):
        broken = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_link, l) for l in links]
            for f in as_completed(futures):
                link, is_broken = f.result()
                if is_broken:
                    broken.append(link)
        return broken

    result.broken_internal = check_links_parallel(all_internal_links)
    result.broken_external = check_links_parallel(all_external_links)
    result.unique_internal = len(all_internal_links)
    result.unique_external = len(all_external_links)
    result.total_crawl_time = round(time.time() - start_time, 2)
    return result
