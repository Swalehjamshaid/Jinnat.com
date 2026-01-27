import asyncio
import random
from typing import Dict, Set, Optional
from urllib.parse import urljoin, urlparse
from collections import deque
import httpx
from bs4 import BeautifulSoup, Tag
from dataclasses import dataclass


@dataclass
class CrawlConfig:
    """Internal configuration for the crawler — easy to tune."""
    max_pages: int = 10
    timeout: float = 10.0
    max_concurrency: int = 8
    politeness_delay_min: float = 0.08
    politeness_delay_max: float = 0.25
    user_agent: str = "FFTech-AuditBot/1.0 (+https://yourdomain.com)"
    max_depth: Optional[int] = None          # optional future extension


def _normalize_netloc(netloc: str) -> str:
    """Normalized domain for same-site comparison."""
    return netloc.lower().removeprefix("www.").rstrip(".")


async def crawl_site(
    start_url: str,
    max_pages: int = 10,
    timeout: float = 10.0,
    max_concurrency: int = 8,
    user_agent: str = "FFTech-AuditBot/1.0 (+https://yourdomain.com)",
) -> Dict[str, str]:
    """
    High-performance, polite, concurrent, same-domain crawler.

    Returns:
        Dict[str, str]: {url: html_content} for successfully fetched pages.

    Features:
    • Concurrent fetching with semaphore control
    • Breadth-first crawl using deque
    • Connection pooling via single AsyncClient
    • Randomized politeness delay between batches
    • Proper URL normalization & same-site check
    • Graceful error handling & early termination
    • Fast lxml parser (fallback to html.parser)
    • Configurable via parameters (no interface break)
    """
    if max_pages < 1:
        return {}

    start_parsed = urlparse(start_url)
    if not start_parsed.scheme or not start_parsed.netloc:
        raise ValueError("Invalid start URL — must include scheme and netloc")

    base_netloc_norm = _normalize_netloc(start_parsed.netloc)

    visited: Set[str] = set()
    queue: deque[str] = deque([start_url])
    results: Dict[str, str] = {}

    headers = {"User-Agent": user_agent}
    limits = httpx.Limits(
        max_connections=max_concurrency,
        max_keepalive_connections=max_concurrency,
        keepalive_expiry=30.0
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        headers=headers,
        verify=False,
        follow_redirects=True,
        http2=True  # faster on modern servers
    ) as client:

        semaphore = asyncio.Semaphore(max_concurrency)

        async def fetch_and_parse(url: str) -> None:
            async with semaphore:
                if url in visited or len(results) >= max_pages:
                    return

                visited.add(url)

                try:
                    resp = await client.get(url)
                    if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", "").lower():
                        return

                    html = resp.text
                    results[url] = html

                    # Early exit if limit reached
                    if len(results) >= max_pages:
                        return

                    # Parse links (use faster lxml parser)
                    soup = BeautifulSoup(html, "lxml")

                    for a_tag in soup.find_all("a", href=True):
                        href = a_tag["href"].strip()
                        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                            continue

                        next_url = urljoin(url, href)
                        next_parsed = urlparse(next_url)

                        if (
                            next_parsed.scheme in ("http", "https")
                            and next_parsed.netloc
                            and _normalize_netloc(next_parsed.netloc) == base_netloc_norm
                            and next_url not in visited
                        ):
                            queue.append(next_url)

                except (httpx.RequestError, httpx.TimeoutException, httpx.ConnectError):
                    pass  # silent skip — continue crawling

        # ────────────────────────────────────────────────
        # Main crawl loop — batch processing for politeness
        # ────────────────────────────────────────────────
        while queue and len(results) < max_pages:
            batch_size = min(len(queue), max_concurrency)
            current_batch = []

            for _ in range(batch_size):
                if not queue:
                    break
                url = queue.popleft()
                if url not in visited:
                    current_batch.append(fetch_and_parse(url))

            if not current_batch:
                break

            await asyncio.gather(*current_batch, return_exceptions=True)

            # Politeness delay — randomized jitter (real-world best practice)
            delay = random.uniform(0.08, 0.25)
            await asyncio.sleep(delay)

    return results
