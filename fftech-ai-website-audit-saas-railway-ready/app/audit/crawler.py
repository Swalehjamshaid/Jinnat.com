import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, defaultdict
from requests.exceptions import RequestException, Timeout, SSLError

# Suppress InsecureRequestWarning (common for international sites)
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


def perform_crawl(start_url: str, max_pages: int = 35) -> CrawlResult:
    """
    Crawls the website starting from start_url, up to max_pages.
    Returns a CrawlResult object with collected data.
    """
    # ────────────────────────────────────────────────
    # Normalize & correct common bad start URLs
    # ────────────────────────────────────────────────
    if not start_url.startswith(('http://', 'https://')):
        start_url = 'https://' + start_url.lstrip('/')

    # Force HTTPS (modern standard)
    start_url = start_url.replace('http://', 'https://')

    # Common fix: if URL points to /login, dashboard, admin, etc. → start from homepage
    path_lower = urlparse(start_url).path.lower()
    fragment_lower = urlparse(start_url).fragment.lower()
    if any(x in path_lower for x in ['/login', '/signin', '/admin', '/dashboard', '/account']) or \
       any(x in fragment_lower for x in ['login', 'signin', 'auth']):
        
        # Extract base domain and try standard homepages
        parsed = urlparse(start_url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"
        
        # Try common homepage patterns (many Pakistani sites use /pk/ or /en/)
        candidates = [
            base_domain + '/',
            base_domain + '/pk/',
            base_domain + '/en/',
            base_domain.rstrip('/') + '/home',
        ]
        
        for candidate in candidates:
            try:
                r = requests.head(candidate, timeout=6, allow_redirects=True, verify=False)
                if 200 <= r.status_code < 400:
                    start_url = candidate
                    print(f"Login/dashboard detected → redirecting crawl to: {start_url}")
                    break
            except:
                pass

    # ────────────────────────────────────────────────
    # Crawl logic
    # ────────────────────────────────────────────────
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
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=(7, 20),  # connect 7s, read 20s
                allow_redirects=True,
                verify=False
            )

            result.status_counts[response.status_code] += 1

            if response.history:
                for r in response.history:
                    result.redirects.append((r.url, r.headers.get('Location')))

            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type:
                continue

            soup = BeautifulSoup(response.text, 'lxml')  # faster parser

            page_data = {
                "url": url,
                "status_code": response.status_code,
                "title": soup.title.string.strip() if soup.title and soup.title.string else None,
                "h1_tags": [h.get_text().strip() for h in soup.find_all('h1')],
                "meta_description": soup.find('meta', attrs={'name': 'description'})['content'] if soup.find('meta', attrs={'name': 'description'}) else None,
                "word_count": len(soup.get_text(separator=' ', strip=True).split()),
                "canonical": soup.find('link', rel='canonical')['href'] if soup.find('link', rel='canonical') else None,
                "robots_meta": soup.find('meta', attrs={'name': 'robots'})['content'] if soup.find('meta', attrs={'name': 'robots'}) else None,
            }
            result.pages.append(page_data)

            # Extract links
            for link in soup.find_all('a', href=True):
                href = urljoin(url, link['href'])
                parsed_href = urlparse(href)

                if parsed_href.scheme not in ('http', 'https'):
                    continue

                # Internal link?
                if (parsed_href.netloc == domain or not parsed_href.netloc) and href not in visited:
                    queue.append(href)
                    result.internal_links[url].append(href)
                else:
                    result.external_links_count += 1

        except Timeout:
            result.status_counts['timeout'] += 1
            result.failed_requests += 1
        except SSLError:
            result.status_counts['ssl_error'] += 1
            result.failed_requests += 1
        except RequestException as e:
            result.status_counts[0] += 1
            result.failed_requests += 1
            if url != start_url:
                result.broken_internal.append({
                    "url": url,
                    "error": str(e)[:120],
                    "from": url
                })

    # Classify broken pages from HTTP status
    for page in result.pages:
        if page["status_code"] >= 400:
            result.broken_internal.append({
                "url": page["url"],
                "status": page["status_code"],
                "type": "http_error"
            })

    return result
