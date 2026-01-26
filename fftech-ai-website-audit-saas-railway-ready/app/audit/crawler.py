# app/audit/crawler.py
import asyncio
import httpx
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import Set, List

@dataclass
class CrawlResult:
    crawled_count: int = 0
    unique_internal: int = 0
    unique_external: int = 0
    broken_internal: List[str] = field(default_factory=list)
    broken_external: List[str] = field(default_factory=list)
    total_crawl_time: float = 0.0

async def fetch_url(client, url, base_domain):
    internal_links, external_links, broken = set(), set(), []
    try:
        resp = await client.get(url, timeout=5)
        if resp.status_code != 200:
            broken.append(url)
            return internal_links, external_links, broken

        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.find_all("a", href=True):
            href = a.get("href")
            if not href or href.startswith("mailto:") or href.startswith("javascript:"):
                continue
            full_url = urljoin(url, href)
            domain = urlparse(full_url).netloc
            if domain == base_domain:
                internal_links.add(full_url)
            else:
                external_links.add(full_url)
    except Exception:
        broken.append(url)
    return internal_links, external_links, broken

async def crawl_async(start_url, max_pages=15):
    from time import time
    start_time = time()
    parsed = urlparse(start_url)
    base_domain = parsed.netloc

    visited, to_visit = set(), set([start_url])
    internal_links_all, external_links_all = set(), set()
    broken_internal, broken_external = [], []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        while to_visit and len(visited) < max_pages:
            tasks = []
            current_batch = list(to_visit)[:max_pages-len(visited)]
            for url in current_batch:
                tasks.append(fetch_url(client, url, base_domain))
                to_visit.remove(url)

            results = await asyncio.gather(*tasks)
            for i, (internal, external, broken) in enumerate(results):
                url = current_batch[i]
                visited.add(url)

                # classify broken
                for b in broken:
                    if urlparse(b).netloc == base_domain:
                        broken_internal.append(b)
                    else:
                        broken_external.append(b)

                # add new internal links
                for link in internal:
                    if link not in visited:
                        to_visit.add(link)

                internal_links_all.update(internal)
                external_links_all.update(external)

    total_crawl_time = round(time() - start_time, 2)
    return CrawlResult(
        crawled_count=len(visited),
        unique_internal=len(internal_links_all),
        unique_external=len(external_links_all),
        broken_internal=broken_internal,
        broken_external=broken_external,
        total_crawl_time=total_crawl_time
    )

def crawl(start_url, max_pages=15):
    return asyncio.run(crawl_async(start_url, max_pages))
