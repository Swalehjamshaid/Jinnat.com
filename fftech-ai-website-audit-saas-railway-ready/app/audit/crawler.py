
import time
from collections import defaultdict, deque
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "FFTechAuditor/2.0 (+https://yourdomain.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

JUNK_EXTENSIONS = (
    ".pdf", ".jpg", ".png", ".jpeg", ".gif", ".webp", ".svg", ".zip",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".mp3", ".mp4"
)


class CrawlResult:
    """Container for crawl outputs."""
    def __init__(self) -> None:
        self.pages: Dict[str, str] = {}
        self.status_counts: Dict[int, int] = defaultdict(int)
        self.internal_links: Dict[str, List[str]] = defaultdict(list)
        self.external_links: Dict[str, List[str]] = defaultdict(list)
        self.broken_internal: List[Tuple[str, str, int]] = []
        self.total_crawl_time: float = 0.0
        self.crawled_count: int = 0

    @property
    def unique_internal(self) -> int:
        s = set()
        for lst in self.internal_links.values():
            s.update(lst)
        return len(s)

    @property
    def unique_external(self) -> int:
        s = set()
        for lst in self.external_links.values():
            s.update(lst)
        return len(s)


def should_crawl(url: str) -> bool:
    url_l = url.lower()
    return not any(url_l.endswith(ext) for ext in JUNK_EXTENSIONS)


def is_same_host(start_url: str, link: str) -> bool:
    return urlparse(start_url).netloc == urlparse(link).netloc


def _head_or_get(session: requests.Session, url: str, timeout: float = 6.0) -> requests.Response:
    """Try HEAD first; fallback to GET on 405/501. Raises on network errors."""
    r = session.head(url, timeout=timeout, allow_redirects=True)
    if r.status_code in (405, 501):
        r = session.get(url, timeout=timeout + 2, stream=True, allow_redirects=True)
    return r


def crawl(
    start_url: str,
    max_pages: int = 20,
    delay: float = 0.35,
    on_progress: Optional[Callable[[int, str], None]] = None,
) -> CrawlResult:
    """Breadth-first crawl within same host with simple politeness and link health checks."""
    start_time = time.time()
    result = CrawlResult()
    queue = deque([start_url])
    seen = set()
    session = requests.Session()
    session.headers.update(HEADERS)

    while queue and len(seen) < max_pages:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        result.crawled_count += 1

        try:
            resp = session.get(url, timeout=12, allow_redirects=True)
            result.status_counts[resp.status_code] += 1
            if resp.status_code != 200:
                if on_progress:
                    pct = min(85, int(len(seen) / max_pages * 80) + 5)
                    on_progress(pct, f"Fetched {len(seen)}/{max_pages} pages…")
                time.sleep(delay)
                continue

            html = resp.text
            result.pages[url] = html

            soup = BeautifulSoup(html, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].split('#')[0].strip()
                if not href or href.startswith(('mailto:', 'javascript:')):
                    continue
                abs_url = urljoin(url, href)
                if not should_crawl(abs_url):
                    continue
                if is_same_host(start_url, abs_url):
                    result.internal_links[url].append(abs_url)
                    if abs_url not in seen:
                        queue.append(abs_url)
                else:
                    result.external_links[url].append(abs_url)
        except Exception:
            result.status_counts[0] += 1

        if on_progress:
            pct = min(85, int(len(seen) / max_pages * 80) + 5)
            on_progress(pct, f"Crawled {len(seen)}/{max_pages} pages…")
        time.sleep(delay)

    # check broken internal links not already fetched
    for from_url, links in result.internal_links.items():
        for to_url in links:
            if to_url in result.pages:
                continue
            try:
                r = _head_or_get(session, to_url, timeout=6.0)
                if r.status_code >= 400:
                    result.broken_internal.append((from_url, to_url, r.status_code))
            except Exception:
                result.broken_internal.append((from_url, to_url, 0))

    result.total_crawl_time = round(time.time() - start_time, 2)
    if on_progress:
        on_progress(95, 'Crawl complete. Assessing link health…')
    return result
