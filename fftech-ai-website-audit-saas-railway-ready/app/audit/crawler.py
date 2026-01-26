# app/audit/crawler.py
import requests, time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {"User-Agent": "FFTechAuditBot/5.0"}

class CrawlResult:
    def __init__(self):
        self.pages = []
        self.visited = set()
        self.unique_internal = 0
        self.unique_external = 0
        self.broken_internal = []
        self.broken_external = []
        self.crawled_count = 0
        self.total_crawl_time = 0

def check_link(url, timeout=5):
    try:
        status = requests.head(url, headers=HEADERS, timeout=timeout, allow_redirects=True).status_code
        return url, status >= 400
    except:
        return url, True

def crawl_site(start_url: str, max_pages=20, delay=0, timeout=5):
    """
    Fast crawl: limited pages, parallel link checks, no unnecessary sleeps.
    """
    domain = urlparse(start_url).netloc
    queue = deque([start_url])
    result = CrawlResult()
    start_time = time.time()

    while queue and len(result.visited) < max_pages and time.time() - start_time < 60:
        url = queue.popleft()
        if url in result.visited:
            continue

        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
        except:
            continue

        result.visited.add(url)
        result.pages.append({"url": url, "html": r.text, "soup": soup})
        result.crawled_count += 1

        internal_links, external_links = set(), set()
        for a in soup.select("a[href]"):
            link = urljoin(url, a["href"].split("#")[0])
            parsed = urlparse(link)
            if not parsed.scheme.startswith("http"):
                continue
            if parsed.netloc == domain:
                internal_links.add(link)
            else:
                external_links.add(link)

        # Parallel broken link checks
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(check_link, link): link for link in internal_links | external_links}
            for f in as_completed(futures):
                link, broken = f.result()
                if link in internal_links and broken:
                    result.broken_internal.append(link)
                elif link in external_links and broken:
                    result.broken_external.append(link)

        # Queue internal links
        for link in internal_links:
            if link not in result.visited:
                queue.append(link)

    result.unique_internal = len(internal_links)
    result.unique_external = len(external_links)
    result.total_crawl_time = round(time.time() - start_time, 2)
    return result

# Alias for runner.py compatibility
crawl = crawl_site
