# app/audit/crawler.py
import time, requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

class CrawlResult:
    def __init__(self):
        self.unique_internal = 0
        self.unique_external = 0
        self.broken_internal = []
        self.broken_external = []
        self.crawled_count = 0
        self.total_crawl_time = 0

def crawl(url: str, max_pages: int = 10, delay: float = 0.01) -> CrawlResult:
    """
    Fast website crawler optimized for speed
    """
    start_time = time.time()
    visited = set()
    to_visit = [url]
    internal_links = set()
    external_links = set()
    broken_internal = []

    session = requests.Session()
    session.headers.update({'User-Agent':'FFTech-AuditBot/4.0'})

    def fetch_links(u):
        try:
            resp = session.get(u, timeout=5, verify=False)
            if resp.status_code >= 400:
                broken_internal.append(u)
            soup = BeautifulSoup(resp.text, "html.parser")
            links = [urljoin(u, a.get("href")) for a in soup.find_all("a", href=True)]
            return links
        except:
            broken_internal.append(u)
            return []

    while to_visit and len(visited) < max_pages:
        current = to_visit.pop(0)
        if current in visited:
            continue
        visited.add(current)
        links = fetch_links(current)
        for link in links:
            parsed = urlparse(link)
            if parsed.netloc == urlparse(url).netloc:
                internal_links.add(link)
                if link not in visited and len(visited)+len(to_visit) < max_pages:
                    to_visit.append(link)
            else:
                external_links.add(link)
        time.sleep(delay)

    result = CrawlResult()
    result.unique_internal = len(internal_links)
    result.unique_external = len(external_links)
    result.broken_internal = broken_internal
    result.broken_external = []  # skip external check for speed
    result.crawled_count = len(visited)
    result.total_crawl_time = round(time.time()-start_time, 2)
    return result
