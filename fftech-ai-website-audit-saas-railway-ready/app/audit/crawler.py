import asyncio
import logging
from collections import deque
from urllib.parse import urljoin, urlparse
from typing import Dict, Set, Optional, Callable

import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup, SoupStrainer

logger = logging.getLogger(__name__)

async def crawl(
    start_url: str,
    max_pages: int = 30,
    concurrency: int = 12,
    timeout: float = 8.0,
    progress_callback: Optional[Callable] = None
) -> Dict:
    """
    Fast & reliable async crawler for SEO/link audit.
    """
    start_time = asyncio.get_event_loop().time()

    start_parsed = urlparse(start_url)
    base_domain = start_parsed.netloc.lower()

    visited: Set[str] = set()
    queue = deque([start_url])
    internal_links: Set[str] = set()
    external_links: Set[str] = set()
    broken_internal: Set[str] = set()
    status_counts: Dict[int, int] = {}

    connector = aiohttp.TCPConnector(limit=40, force_close=False)
    timeout_obj = ClientTimeout(total=timeout)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout_obj) as session:
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch(url: str):
            async with semaphore:
                try:
                    async with session.get(url, allow_redirects=True) as resp:
                        status = resp.status
                        status_counts[status] = status_counts.get(status, 0) + 1

                        if status >= 400:
                            if urlparse(url).netloc.lower() == base_domain:
                                broken_internal.add(url)
                            return None, status

                        content_type = resp.headers.get('content-type', '').lower()
                        if 'text/html' not in content_type:
                            return None, status

                        html = await resp.text()
                        return html, status

                except Exception as e:
                    logger.debug(f"Request failed {url}: {type(e).__name__}")
                    status_counts[0] = status_counts.get(0, 0) + 1
                    return None, 0

        crawled_count = 0
        tasks = []

        while queue and crawled_count < max_pages:
            # Fill batch
            while len(tasks) < concurrency and queue:
                url = queue.popleft()
                if url in visited:
                    continue
                visited.add(url)
                tasks.append(asyncio.create_task(fetch(url)))
                crawled_count += 1

                if progress_callback:
                    pct = round(crawled_count / max_pages * 100, 1)
                    await progress_callback({
                        "status": f"Crawling pages... ({crawled_count}/{max_pages})",
                        "crawl_progress": pct,
                        "finished": False
                    })

            if not tasks:
                break

            done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for fut in done:
                html, status = await fut
                if html is None:
                    continue

                # Parse only links + important head tags
                soup = BeautifulSoup(
                    html,
                    "lxml",
                    parse_only=SoupStrainer(["a", "link", "meta", "title"])
                )

                for tag in soup.find_all("a", href=True):
                    href = tag["href"].strip()
                    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                        continue

                    full_url = urljoin(url, href)
                    parsed = urlparse(full_url)

                    if not parsed.scheme or not parsed.netloc:
                        continue

                    if parsed.netloc.lower() == base_domain:
                        if full_url not in visited and full_url not in queue:
                            queue.append(full_url)
                        internal_links.add(full_url)
                    else:
                        external_links.add(full_url)

        # Cleanup remaining tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    total_time = asyncio.get_event_loop().time() - start_time

    return {
        "crawled_count": len(visited),
        "unique_internal": len(internal_links),
        "unique_external": len(external_links),
        "broken_internal": len(broken_internal),
        "status_counts": status_counts,
        "total_crawl_time": round(total_time, 2)
    }
