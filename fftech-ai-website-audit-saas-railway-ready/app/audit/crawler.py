import time
import requests
from urllib.parse import urljoin, urlparse
from collections import defaultdict, deque
from bs4 import BeautifulSoup
from typing import Optional

JUNK_EXTENSIONS = (
    '.pdf', '.jpg', '.png', '.jpeg', '.gif', '.webp', '.svg', '.zip',
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.mp3', '.mp4'
)

HEADERS = {
    'User-Agent': 'FFTechAuditor/2.0 (+https://yourdomain.com; contact@email.com)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

class CrawlResult:
    def __init__(self):
        self.pages: dict[str, str] = {}                    # url → html (only if 200)
        self.status_counts: dict[int, int] = defaultdict(int)
        self.internal_links: dict[str, list[str]] = defaultdict(list)
        self.external_links: dict[str, list[str]] = defaultdict(list)
        self.broken_internal: list[tuple[str, str, int]] = []   # (from_url, bad_url, status)
        self.broken_external: list[tuple[str, str, int]] = []   # optional
        self.total_crawl_time: float = 0.0
        self.crawled_count: int = 0

def is_same_host(start_url: str, link: str) -> bool:
    """True if both URLs have the same domain (netloc)"""
    return urlparse(start_url).netloc == urlparse(link).netloc

def should_crawl(url: str) -> bool:
    """Skip non-HTML junk files"""
    return not any(url.lower().endswith(ext) for ext in JUNK_EXTENSIONS)

def crawl(
    start_url: str,
    max_pages: int = 15,
    timeout: int = 8,
    delay: float = 0.4,           # polite delay between requests (seconds)
    check_external: bool = False  # set True to also verify external links
) -> CrawlResult:
    start_time = time.time()
    result = CrawlResult()

    queue = deque([start_url])
    seen = set()

    session = requests.Session()  # reuse connection → faster & more reliable
    session.headers.update(HEADERS)

    while queue and len(seen) < max_pages:
        url = queue.popleft()

        if url in seen:
            continue
        seen.add(url)
        result.crawled_count += 1

        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            status = resp.status_code
            result.status_counts[status] += 1

            if status != 200:
                # We can still collect broken links from parent pages
                continue

            html = resp.text
            result.pages[url] = html

            soup = BeautifulSoup(html, "html.parser")  # very robust parser

            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                    continue

                abs_url = urljoin(url, href)

                # Clean up fragment identifiers
                abs_url = abs_url.split('#')[0]

                if not should_crawl(abs_url):
                    continue

                if is_same_host(start_url, abs_url):
                    result.internal_links[url].append(abs_url)
                    if abs_url not in seen:
                        queue.append(abs_url)
                else:
                    result.external_links[url].append(abs_url)

        except (requests.RequestException, UnicodeDecodeError, ValueError) as e:
            result.status_counts[0] += 1  # 0 = error
            print(f"Error crawling {url}: {e}")

        time.sleep(delay)  # Be nice to servers

    # Optional: verify internal broken links
    print("Checking internal links for broken ones...")
    for from_url in list(result.internal_links.keys()):
        for to_url in result.internal_links[from_url]:
            if to_url in result.pages:  # already crawled → must be ok
                continue
            try:
                r = session.head(to_url, timeout=6, allow_redirects=True)
                if r.status_code >= 400:
                    result.broken_internal.append((from_url, to_url, r.status_code))
            except requests.RequestException:
                result.broken_internal.append((from_url, to_url, 0))

    result.total_crawl_time = round(time.time() - start_time, 2)
    return result


# ────────────────────────────────────────────────
# Example usage & pretty print
# ────────────────────────────────────────────────

if __name__ == "__main__":
    url = "https://www.haier.com.pk"   # or your test site
    print(f"Crawling: {url}\n")

    result = crawl(url, max_pages=20, timeout=10, delay=0.5)

    print(f"Finished in {result.total_crawl_time} seconds")
    print(f"Crawled {result.crawled_count} pages")
    print("\nStatus codes:")
    for code, count in sorted(result.status_counts.items()):
        print(f"  {code}: {count}")

    print(f"\nBroken internal links found: {len(result.broken_internal)}")
    for from_url, bad_url, code in result.broken_internal[:8]:  # show first few
        print(f"  {code} ← {from_url} → {bad_url}")

    print(f"\nInternal pages discovered: {len(result.internal_links)}")
    print(f"External links discovered: {sum(len(v) for v in result.external_links.values())}")
