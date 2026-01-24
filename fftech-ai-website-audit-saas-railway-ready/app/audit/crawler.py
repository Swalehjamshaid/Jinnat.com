import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import defaultdict
import time
import logging

logger = logging.getLogger("crawler_engine")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FFTechAuditor/2.0; +https://fftech.ai)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

JUNK_EXTENSIONS = ('.pdf', '.jpg', '.png', '.zip', '.docx', '.jpeg', '.gif')


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
    except:
        return False


async def fetch_page(session: aiohttp.ClientSession, url: str, timeout: int = 7):
    """Fetch a page content async"""
    try:
        async with session.get(url, timeout=timeout) as resp:
            text = await resp.text()
            return url, resp.status, resp.headers.get("Content-Type", ""), text
    except:
        return url, 0, "", ""


async def check_link(session: aiohttp.ClientSession, link: str):
    """Check if a link is broken using HEAD (fast)"""
    try:
        async with session.head(link, timeout=3, allow_redirects=True) as resp:
            return link, resp.status
    except:
        return link, 0


async def crawl(start_url: str, max_pages: int = 15, timeout: int = 7) -> CrawlResult:
    """
    Async world-class crawler:
    - Async requests for parallelism
    - Skip junk extensions and non-HTML pages
    - Limit broken link checks for speed
    """
    start_time = time.time()
    result = CrawlResult()
    queue = [start_url]
    seen = set()

    connector = aiohttp.TCPConnector(limit=20)  # 20 concurrent requests
    async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:

        while queue and len(seen) < max_pages:
            tasks = []
            for url in queue[:max_pages - len(seen)]:
                if url in seen: continue
                seen.add(url)
                tasks.append(fetch_page(session, url, timeout))
            queue = []

            pages = await asyncio.gather(*tasks)
            for url, status, content_type, html in pages:
                result.status_counts[status] += 1
                if status != 200 or "text/html" not in content_type.lower() or not html:
                    continue

                result.pages[url] = html
                soup = BeautifulSoup(html, "html.parser")

                for tag in soup.find_all("a", href=True):
                    href = tag.get("href", "").strip()
                    if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
                        continue
                    if any(href.lower().endswith(ext) for ext in JUNK_EXTENSIONS):
                        continue

                    abs_url = urljoin(url, href)
                    if is_same_host(start_url, abs_url):
                        result.internal_links[url].append(abs_url)
                        if abs_url not in seen:
                            queue.append(abs_url)
                    else:
                        result.external_links[url].append(abs_url)

        # --- Broken Link Check ---
        all_internal = [link for links in result.internal_links.values() for link in links]
        all_internal = list(set(all_internal))[:50]  # Limit to 50 links
        tasks = [check_link(session, l) for l in all_internal]
        check_results = await asyncio.gather(*tasks)
        for link, status in check_results:
            if status >= 400 or status == 0:
                # Find source page
                src = next((k for k, v in result.internal_links.items() if link in v), None)
                result.broken_internal.append((src, link, status))

    result.total_crawl_time = round(time.time() - start_time, 2)
    return result

