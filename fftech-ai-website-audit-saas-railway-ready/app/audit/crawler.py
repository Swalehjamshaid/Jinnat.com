# app/audit/crawler.py

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
from collections import deque, defaultdict
import logging

logger = logging.getLogger("crawler")
logger.setLevel(logging.INFO)

HEADERS = {"User-Agent": "FFTechAuditor/2.0 (+https://fftech.ai)"}

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

def normalize_url(url: str) -> str:
    url, _ = urldefrag(url)
    return url.rstrip('/')

async def fetch(session: aiohttp.ClientSession, url: str, timeout: int):
    try:
        async with session.get(url, headers=HEADERS, timeout=timeout) as resp:
            content_type = resp.headers.get('Content-Type', '')
            text = await resp.text() if 'text/html' in content_type else ''
            return resp.status, text, content_type
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return 0, '', ''

async def check_link(session: aiohttp.ClientSession, url: str, timeout: int):
    try:
        async with session.head(url, headers=HEADERS, timeout=timeout, allow_redirects=True) as resp:
            return resp.status
    except Exception:
        return 0

async def crawl_async(start_url: str, max_pages: int = 50, timeout: int = 10) -> CrawlResult:
    q = deque([start_url])
    seen = set()
    result = CrawlResult()

    async with aiohttp.ClientSession() as session:
        while q and len(seen) < max_pages:
            url = normalize_url(q.popleft())
            if url in seen:
                continue
            seen.add(url)

            status, html, content_type = await fetch(session, url, timeout)
            result.status_counts[status] += 1

            if 'text/html' not in content_type:
                continue

            soup = BeautifulSoup(html, 'html.parser')
            result.pages[url] = html

            for a in soup.find_all('a', href=True):
                href = normalize_url(urljoin(url, a['href']))
                if href.startswith('mailto:') or href.startswith('tel:'):
                    continue
                if is_same_host(start_url, href):
                    result.internal_links[url].append(href)
                    if href not in seen and len(seen) + len(q) < max_pages:
                        q.append(href)
                else:
                    result.external_links[url].append(href)

        # Check broken internal links
        tasks = [check_link(session, l, timeout) for links in result.internal_links.values() for l in links]
        internal_statuses = await asyncio.gather(*tasks, return_exceptions=True)
        i = 0
        for src, links in result.internal_links.items():
            for link in links:
                status = internal_statuses[i] if isinstance(internal_statuses[i], int) else 0
                if status >= 400 or status == 0:
                    result.broken_internal.append((src, link, status))
                i += 1

        # Check broken external links (limit 50 per page)
        tasks = [check_link(session, l, timeout) for links in result.external_links.values() for l in links[:50]]
        external_statuses = await asyncio.gather(*tasks, return_exceptions=True)
        i = 0
        for src, links in result.external_links.items():
            for link in links[:50]:
                status = external_statuses[i] if isinstance(external_statuses[i], int) else 0
                if status >= 400 or status == 0:
                    result.broken_external.append((src, link, status))
                i += 1

    return result

def crawl(start_url: str, max_pages: int = 50, timeout: int = 10) -> CrawlResult:
    """Synchronous wrapper for async crawler."""
    return asyncio.run(crawl_async(start_url, max_pages=max_pages, timeout=timeout))
