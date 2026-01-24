# app/audit/crawler.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, defaultdict
import time

# Custom User-Agent to identify your bot to webmasters
HEADERS = {
    "User-Agent": "FFTechAuditor/1.0 (+https://fftech.ai)",
    "Accept": "text/html,application/xhtml+xml"
}

class CrawlResult:
    def __init__(self):
        self.pages = {}  # URL: HTML content
        self.status_counts = defaultdict(int)  # HTTP status distribution
        self.internal_links = defaultdict(list)
        self.external_links = defaultdict(list)
        self.broken_internal = []  # (source, target, status)
        self.broken_external = []
        self.total_crawl_time = 0


def is_same_host(start_url: str, link: str) -> bool:
    """Ensures we stay on the user's domain during the crawl."""
    try:
        return urlparse(start_url).netloc == urlparse(link).netloc
    except Exception:
        return False


def crawl(start_url: str, max_pages: int = 50, timeout: int = 10) -> CrawlResult:
    """
    Performs a BFS crawl of the start_url up to max_pages.
    INPUT / OUTPUT IS STRICTLY PRESERVED
    """
    start_time = time.time()
    queue = deque([start_url])
    seen = set()
    result = CrawlResult()

    session = requests.Session()
    session.headers.update(HEADERS)

    # ==========================
    # 1. MAIN DISCOVERY LOOP
    # ==========================
    while queue and len(seen) < max_pages:
        url = queue.popleft()

        if url in seen:
            continue

        seen.add(url)

        try:
            response = session.get(
                url,
                timeout=timeout,
                allow_redirects=True
            )

            status_code = response.status_code
            result.status_counts[status_code] += 1

            content_type = response.headers.get("Content-Type", "")

            # Only parse HTML pages
            if "text/html" not in content_type.lower():
                continue

            html = response.text
            result.pages[url] = html

            soup = BeautifulSoup(html, "html.parser")

            for tag in soup.find_all("a", href=True):
                href = tag.get("href", "").strip()

                # Ignore non-web links
                if not href or href.startswith(
                    ("mailto:", "tel:", "javascript:", "#")
                ):
                    continue

                absolute_url = urljoin(url, href)

                if is_same_host(start_url, absolute_url):
                    result.internal_links[url].append(absolute_url)
                    if absolute_url not in seen:
                        queue.append(absolute_url)
                else:
                    result.external_links[url].append(absolute_url)

        except requests.RequestException:
            # Network or timeout failure
            result.status_counts[0] += 1
        except Exception:
            # Parsing or unexpected failure
            result.status_counts[0] += 1

    # ==========================
    # 2. INTERNAL LINK VALIDATION
    # ==========================
    checked_internal = set()

    for source, links in result.internal_links.items():
        for link in links:
            if link in checked_internal:
                continue

            checked_internal.add(link)

            try:
                head_response = session.head(
                    link,
                    timeout=5,
                    allow_redirects=True
                )

                if head_response.status_code >= 400:
                    result.broken_internal.append(
                        (source, link, head_response.status_code)
                    )

            except requests.RequestException:
                result.broken_internal.append((source, link, 0))
            except Exception:
                result.broken_internal.append((source, link, 0))

    # ==========================
    # 3. EXTERNAL LINK VALIDATION
    # ==========================
    checked_external = set()

    for source, links in result.external_links.items():
        for link in links[:20]:  # Limit external checks for safety
            if link in checked_external:
                continue

            checked_external.add(link)

            try:
                head_response = session.head(
                    link,
                    timeout=5,
                    allow_redirects=True
                )

                if head_response.status_code >= 400:
                    result.broken_external.append(
                        (source, link, head_response.status_code)
                    )

            except requests.RequestException:
                result.broken_external.append((source, link, 0))
            except Exception:
                result.broken_external.append((source, link, 0))

    result.total_crawl_time = round(time.time() - start_time, 2)
    return result
