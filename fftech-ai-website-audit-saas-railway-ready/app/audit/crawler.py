# app/audit/crawler.py
import requests, time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque

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

def crawl_site(start_url: str, max_pages=40, delay=0.15, timeout=8):
    """
    Crawl a website and collect pages, internal/external links, broken links.
    """
    domain = urlparse(start_url).netloc
    queue = deque([start_url])
    result = CrawlResult()
    start_time = time.time()

    while queue and len(result.visited) < max_pages and time.time() - start_time < 90:
        url = queue.popleft()
        if url in result.visited:
            continue

        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
        except Exception:
            continue

        result.visited.add(url)
        result.pages.append({"url": url, "html": r.text, "soup": soup})
        result.crawled_count += 1

        internal_links = set()
        external_links = set()

        for a in soup.select("a[href]"):
            link = urljoin(url, a["href"].split("#")[0])
            parsed_link = urlparse(link)
            if not parsed_link.scheme.startswith("http"):
                continue

            if parsed_link.netloc == domain:
                internal_links.add(link)
            else:
                external_links.add(link)

        result.unique_internal = len(internal_links)
        result.unique_external = len(external_links)

        # Check for broken links
        for link in internal_links:
            try:
                if requests.head(link, headers=HEADERS, timeout=timeout).status_code >= 400:
                    result.broken_internal.append(link)
            except:
                result.broken_internal.append(link)

        for link in external_links:
            try:
                if requests.head(link, headers=HEADERS, timeout=timeout).status_code >= 400:
                    result.broken_external.append(link)
            except:
                result.broken_external.append(link)

        for link in internal_links:
            if link not in result.visited:
                queue.append(link)

        time.sleep(delay)

    result.total_crawl_time = round(time.time() - start_time, 2)
    return result

# Alias for runner.py compatibility
crawl = crawl_site
