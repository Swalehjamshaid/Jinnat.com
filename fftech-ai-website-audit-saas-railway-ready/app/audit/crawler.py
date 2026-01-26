# app/audit/crawler.py
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
    max_pages: int = 20,               # lowered for speed
    max_depth: int = 3,
    concurrency: int = 15,
    timeout: float = 6.0,
    progress_callback: Optional[Callable] = None
) -> Dict:
    start_time = asyncio.get_event_loop().time()

    parsed_start = urlparse(start_url)
    base_domain = parsed_start.netloc.lower()

    visited: Set[str] = set()
    queue = deque([(start_url, 0)])  # (url, depth)
    internal: Set[str] = set()
    external: Set[str] = set()
    broken: Set[str] = set()
    status_counts: Dict[int, int] = {}

    connector = aiohttp.TCPConnector(limit=60, ssl=False)  # ssl=False for speed (fix in production)
    timeout_obj = ClientTimeout(total=timeout)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout_obj) as session:
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch(url: str, depth: int):
            if depth > max_depth:
                return None

            async with semaphore:
                try:
                    async with session.get(url, allow_redirects=True) as resp:
                        status = resp.status
                        status_counts[status] = status_counts.get(status, 0) + 1

                        if status >= 400:
                            if urlparse(url).netloc.lower() == base_domain:
                                broken.add(url)
                            return None

                        if 'text/html' not in resp.headers.get('content-type', '').lower():
                            return None

                        return await resp.text()

                except Exception:
                    status_counts[0] = status_counts.get(0, 0) + 1
                    return None

        crawled = 0
        tasks = []

        while queue and crawled < max_pages:
            while len(tasks) < concurrency and queue:
                url, depth = queue.popleft()
                if url in visited:
                    continue
                visited.add(url)
                tasks.append(asyncio.create_task(fetch(url, depth)))
                crawled += 1

                if progress_callback:
                    pct = min(round(crawled / max_pages * 100, 1), 99)
                    await progress_callback({
                        "status": f"Crawling pages... ({crawled}/{max_pages})",
                        "crawl_progress": pct,
                        "finished": False
                    })

            if not tasks:
                break

            done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for fut in done:
                html = await fut
                if html is None:
                    continue

                soup = BeautifulSoup(
                    html,
                    "lxml",
                    parse_only=SoupStrainer(["a", "link", "meta", "title"])
                )

                for tag in soup.find_all("a", href=True):
                    href = tag["href"].strip()
                    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                        continue

                    full = urljoin(url, href)
                    parsed = urlparse(full)

                    if not parsed.scheme or not parsed.netloc:
                        continue

                    if parsed.netloc.lower() == base_domain:
                        if full not in visited and full not in queue:
                            queue.append((full, depth + 1))
                        internal.add(full)
                    else:
                        external.add(full)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    total_time = asyncio.get_event_loop().time() - start_time

    return {
        "crawled_count": len(visited),
        "unique_internal": len(internal),
        "unique_external": len(external),
        "broken_internal": len(broken),
        "status_counts": status_counts,
        "total_crawl_time": round(total_time, 2)
    }
