# app/audit/crawler.py
import logging
import time
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import Set, List
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger('audit_engine')


@dataclass
class CrawlResult:
    crawled_count: int = 0
    unique_internal: int = 0
    unique_external: int = 0
    broken_internal: List[str] = field(default_factory=list)
    broken_external: List[str] = field(default_factory=list)
    total_crawl_time: float = 0.0


def fetch_url(url: str, base_domain: str):
    """Fetch a URL and return links"""
    internal_links = set()
    external_links = set()
    broken_links = []

    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            broken_links.append(url)
            return internal_links, external_links, broken_links

        soup = BeautifulSoup(resp.text, "html.parser")
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
        broken_links.append(url)

    return internal_links, external_links, broken_links


def crawl(start_url: str, max_pages: int = 50, delay: float = 0.05) -> CrawlResult:
    """
    Crawl site for internal/external/broken links
    Optimized for speed: multi-threaded, minimal delay
    """
    start_time = time.time()
    parsed = urlparse(start_url)
    base_domain = parsed.netloc

    visited: Set[str] = set()
    to_visit: Set[str] = set([start_url])
    internal_links_all: Set[str] = set()
    external_links_all: Set[str] = set()
    broken_internal: List[str] = []
    broken_external: List[str] = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        while to_visit and len(visited) < max_pages:
            futures = {}
            for url in list(to_visit)[:max_pages - len(visited)]:
                futures[executor.submit(fetch_url, url, base_domain)] = url
                to_visit.remove(url)

            for future in futures:
                try:
                    internal_links, external_links, broken = future.result()
                    url = futures[future]
                    visited.add(url)

                    # Classify broken links
                    for b in broken:
                        if urlparse(b).netloc == base_domain:
                            broken_internal.append(b)
                        else:
                            broken_external.append(b)

                    # Add new links
                    for link in internal_links:
                        if link not in visited:
                            to_visit.add(link)
                    internal_links_all.update(internal_links)
                    external_links_all.update(external_links)

                except Exception as e:
                    logger.error("Crawl error: %s", e)
            if delay > 0:
                time.sleep(delay)

    total_crawl_time = round(time.time() - start_time, 2)
    result = CrawlResult(
        crawled_count=len(visited),
        unique_internal=len(internal_links_all),
        unique_external=len(external_links_all),
        broken_internal=broken_internal,
        broken_external=broken_external,
        total_crawl_time=total_crawl_time
    )
    return result
