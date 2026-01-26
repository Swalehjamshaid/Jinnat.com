import asyncio
import logging
from collections import deque
from urllib.parse import urljoin, urlparse
from typing import Set, Dict

import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup, SoupStrainer

logger = logging.getLogger(__name__)

async def crawl(start_url: str, max_pages: int = 30, concurrency: int = 10, timeout: float = 8.0) -> Dict:
    """
    Fast async crawler for SEO/link audit.
    - Concurrent requests with semaphore
    - Connection pooling
    - Only parses links + meta/title
    - Same-domain filtering
    """
    start_time = asyncio.get_event_loop().time()

    parsed_start = urlparse(start_url)
    base_domain = parsed_start.netloc.lower()

    visited: Set[str] = set()
    queue = deque([start_url])
    internal = set()
    external = set()
    broken = set()
    status_count = {}

    connector = aiohttp.TCPConnector(limit=30)
    timeout_obj = ClientTimeout(total=timeout)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout_obj) as session:
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch(url: str):
            async with semaphore:
                try:
                    async with session.get(url, allow_redirects=True) as resp:
                        status = resp.status
                        status_count[status] = status_count.get(status, 0) + 1

                        if status >= 400:
                            if urlparse(url).netloc.lower() == base_domain:
                                broken.add(url)
                            return None

                        content_type = resp.headers.get('content-type', '').lower()
                        if 'text/html' not in content_type:
                            return None

                        html = await resp.text()
                        return html

                except Exception as e:
                    logger.debug(f"Fetch failed {url}: {e}")
                    status_count[0] = status_count.get(0, 0) + 1
                    return None

        crawled = 0
        tasks = []

        while queue and crawled < max_pages:
            # Fill batch
            while len(tasks) < concurrency and queue:
                url = queue.popleft()
                if url in visited:
                    continue
                visited.add(url)
                tasks.append(asyncio.create_task(fetch(url)))
                crawled += 1

            if not tasks:
                break

            # Wait for some to finish
            done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for fut in done:
                html = await fut
                if html is None:
                    continue

                # Minimal parsing: only links + head elements
                soup = BeautifulSoup(html, 'lxml', parse_only=SoupStrainer(['a', 'link', 'meta', 'title']))

                for tag in soup.find_all('a', href=True):
                    href = tag['href'].strip()
                    if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                        continue
                    full = urljoin(url, href)
                    parsed = urlparse(full)

                    if parsed.netloc.lower() == base_domain:
                        if full not in visited and full not in queue:
                            queue.append(full)
                        internal.add(full)
                    else:
                        external.add(full)

        # Cleanup remaining tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    total_time = asyncio.get_event_loop().time() - start_time

    return {
        "crawled_count": len(visited),
        "unique_internal": len(internal),
        "unique_external": len(external),
        "broken_internal": len(broken),
        "status_counts": status_count,
        "total_crawl_time": round(total_time, 2)
    }
