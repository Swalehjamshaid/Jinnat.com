import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, defaultdict
from requests.exceptions import RequestException, Timeout, SSLError

# Suppress only the InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "FFTechAuditor/1.0 (+https://fftech.ai)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class CrawlResult:
    def __init__(self):
        self.pages = []                     # list of dicts with page info
        self.status_counts = defaultdict(int)
        self.internal_links = defaultdict(list)   # url → list of internal links found
        self.broken_internal = []           # list of broken internal URLs (404, etc.)
        self.redirects = []                 # list of (from_url, to_url) tuples
        self.external_links_count = 0
        self.failed_requests = 0


def perform_crawl(start_url: str, max_pages: int = 10) -> CrawlResult:
    """
    Crawls the website starting from start_url, up to max_pages.
    Returns a CrawlResult object with collected data.
    """
    if not start_url.startswith(('http://', 'https://')):
        start_url = 'https://' + start_url

    visited = set()
    queue = deque([start_url])
    result = CrawlResult()

    domain = urlparse(start_url).netloc

    while queue and len(visited) < max_pages:
        url = queue.popleft()

        if url in visited:
            continue

        visited.add(url)

        try:
            # Try with timeout and SSL verification disabled (for problematic certs)
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=12,
                allow_redirects=True,
                verify=False
            )

            result.status_counts[response.status_code] += 1

            # Handle redirects (record them)
            if response.history:
                for r in response.history:
                    result.redirects.append((r.url, r.headers.get('Location')))

            # Only process HTML content
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type:
                continue

            soup = BeautifulSoup(response.text, 'html.parser')

            # Collect page data
            page_data = {
                "url": url,
                "status_code": response.status_code,
                "title": soup.title.string.strip() if soup.title and soup.title.string else None,
                "h1_tags": [h.get_text().strip() for h in soup.find_all('h1')],
                "meta_description": (
                    soup.find('meta', attrs={'name': 'description'})['content']
                    if soup.find('meta', attrs={'name': 'description'})
                    else None
                ),
                "word_count": len(soup.get_text().split()),
            }
            result.pages.append(page_data)

            # Find all links
            for link in soup.find_all('a', href=True):
                href = urljoin(url, link['href'])
                parsed_href = urlparse(href)

                # Skip invalid / javascript: / mailto: etc.
                if not parsed_href.scheme in ('http', 'https'):
                    continue

                # Internal link?
                if parsed_href.netloc == domain or not parsed_href.netloc:
                    result.internal_links[url].append(href)
                    if href not in visited:
                        queue.append(href)
                else:
                    result.external_links_count += 1

        except Timeout:
            result.status_counts['timeout'] += 1
            result.failed_requests += 1
        except SSLError:
            result.status_counts['ssl_error'] += 1
            result.failed_requests += 1
        except RequestException as e:
            # 404, 500, connection error, etc.
            result.status_counts[0] += 1
            result.failed_requests += 1
            # Consider this URL broken if internal
            if url != start_url:  # don't mark start_url as broken
                result.broken_internal.append({
                    "url": url,
                    "error": str(e)
                })

    # After crawl: check internal links for broken ones (simple status check)
    # Note: this is optional and can be expensive — only do for small crawls
    if max_pages <= 20:
        for page in result.pages:
            if page["status_code"] >= 400:
                result.broken_internal.append({
                    "url": page["url"],
                    "status": page["status_code"]
                })

    return result
