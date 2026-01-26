import asyncio
import logging
from collections import deque
from urllib.parse import urljoin, urlparse
from typing import NamedTuple, Set, Dict

import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class CrawlResult(NamedTuple):
    crawled_count: int = 0
    unique_internal: int = 0
    unique_external: int = 0
    broken_internal: int = 0
    status_counts: Dict[int, int] = None
    total_crawl_time: float = 0.0

async def crawl(start_url: str, max_pages: int = 30, delay: float = 0.15, timeout: float = 8.0) -> CrawlResult:
    """
    Fast async crawler optimized for SEO/link audit.
    - Uses aiohttp connection pooling
    - Concurrent requests (controlled concurrency)
    - Early exit on head/meta only when possible
    - Minimal HTML parsing
    - Smart same-host filtering
    """
    start_time = asyncio.get_event_loop().time()

    parsed_start = urlparse(start_url)
    base_domain = parsed_start.netloc

    visited: Set[str] = set()
    queue = deque([start_url])
    internal_links = set()
    external_links = set()
    broken_internal = set()
    status_counts = {}

    connector = aiohttp.TCPConnector(limit=30, force_close=False)  # pool connections
    timeout_obj = ClientTimeout(total=timeout)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout_obj) as session:
        semaphore = asyncio.Semaphore(12)  # concurrency limit – tune between 8–20

        async def fetch_page(url: str):
            async with semaphore:
                try:
                    async with session.get(url, allow_redirects=True) as resp:
                        status = resp.status
                        status_counts[status] = status_counts.get(status, 0) + 1

                        if status >= 400:
                            if url.startswith(start_url):
                                broken_internal.add(url)
                            return None, status

                        if status in (301, 302, 307, 308):
                            # follow redirect in queue if needed
                            return None, status

                        # Early exit for non-HTML
                        content_type = resp.headers.get('content-type', '').lower()
                        if 'text/html' not in content_type:
                            return None, status

                        html = await resp.text()
                        return html, status

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.debug(f"Fetch error {url}: {e}")
                    status_counts[0] = status_counts.get(0, 0) + 1
                    return None, 0

        tasks = []
        crawled = 0

        while queue and crawled < max_pages:
            if not tasks:
                # fill batch
                batch_size = min(semaphore._value, len(queue), 12)
                for _ in range(batch_size):
                    if not queue:
                        break
                    url = queue.popleft()
                    if url in visited:
                        continue
                    visited.add(url)
                    tasks.append(asyncio.create_task(fetch_page(url)))
                    crawled += 1

            # Wait for first task in batch to finish
            done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for fut in done:
                html, status = await fut
                if html is None:
                    continue

                soup = BeautifulSoup(html, 'lxml', parse_only=BeautifulSoup.SoupStrainer(['a', 'link', 'meta', 'title']))

                # Extract links
                for link in soup.find_all('a', href=True):
                    href = link['href'].strip()
                    if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                        continue
                    full_url = urljoin(url, href)
                    parsed = urlparse(full_url)

                    if not parsed.scheme or not parsed.netloc:
                        continue

                    if parsed.netloc == base_domain:
                        if full_url not in visited and full_url not in queue:
                            queue.append(full_url)
                        internal_links.add(full_url)
                    else:
                        external_links.add(full_url)

                # Optional: early stop if queue too large
                if len(queue) > max_pages * 3:
                    queue = deque(list(queue)[:max_pages * 2])

        await asyncio.gather(*tasks, return_exceptions=True)  # cleanup

    total_time = asyncio.get_event_loop().time() - start_time

    return CrawlResult(
        crawled_count=len(visited),
        unique_internal=len(internal_links),
        unique_external=len(external_links),
        broken_internal=len(broken_internal),
        status_counts=status_counts,
        total_crawl_time=total_time
    )
