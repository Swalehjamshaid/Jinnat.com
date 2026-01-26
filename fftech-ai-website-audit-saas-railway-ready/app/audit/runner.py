# app/audit/crawler.py

import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
from dataclasses import dataclass, field

HEADERS = {
    "User-Agent": "FFTechAuditBot/5.0",
    "Accept": "text/html,application/xhtml+xml"
}

# ---------- Result Object (Used by runner.py) ----------
@dataclass
class CrawlResult:
    crawled_count: int = 0
    total_crawl_time: float = 0.0

    unique_internal: int = 0
    unique_external: int = 0

    broken_internal: list = field(default_factory=list)
    broken_external: list = field(default_factory=list)


# ---------- Core Crawler ----------
def crawl(start_url: str, max_pages: int = 50, delay: float = 0.15) -> CrawlResult:
    """
    High-speed audit crawler
    - Internal / External links
    - Broken link detection
    - Domain-safe
    """

    start_time = time.time()
    result = CrawlResult()

    parsed_start = urlparse(start_url)
    domain = parsed_start.netloc

    visited = set()
    internal_links = set()
    external_links = set()

    queue = deque([start_url])
    session = requests.Session()
    session.headers.update(HEADERS)

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue

        try:
            response = session.get(url, timeout=8, allow_redirects=True)
            status = response.status_code
            if status >= 400:
                result.broken_internal.append(url)
                continue

            soup = BeautifulSoup(response.text, "html.parser")

        except Exception:
            result.broken_internal.append(url)
            continue

        visited.add(url)
        result.crawled_count += 1

        # ---- Parse links ----
        for tag in soup.select("a[href]"):
            href = tag.get("href").strip()
            if not href or href.startswith(("mailto:", "tel:", "javascript:")):
                continue

            link = urljoin(url, href.split("#")[0])
            parsed = urlparse(link)

            if not parsed.scheme.startswith("http"):
                continue

            # Internal
            if parsed.netloc == domain:
                internal_links.add(link)
                if link not in visited:
                    queue.append(link)
            else:
                external_links.add(link)

        time.sleep(delay)

    # ---- External link validation (FAST HEAD check) ----
    for ext in list(external_links)[:25]:  # limit for speed
        try:
            r = session.head(ext, timeout=6, allow_redirects=True)
            if r.status_code >= 400:
                result.broken_external.append(ext)
        except Exception:
            result.broken_external.append(ext)

    result.unique_internal = len(internal_links)
    result.unique_external = len(external_links)
    result.total_crawl_time = round(time.time() - start_time, 2)

    return result
