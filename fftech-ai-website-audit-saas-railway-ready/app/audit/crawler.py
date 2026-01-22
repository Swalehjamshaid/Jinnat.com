import requests
import urllib3
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
from collections import deque, defaultdict
from requests.exceptions import RequestException, Timeout, SSLError

# Optional JS rendering (safe fallback)
try:
    from playwright.sync_api import sync_playwright
    JS_AVAILABLE = True
except:
    JS_AVAILABLE = False

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "FFTechAuditor/1.2 (+https://fftech.ai)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class CrawlResult:
    def __init__(self):
        self.pages = []
        self.status_counts = defaultdict(int)
        self.internal_links = defaultdict(list)
        self.broken_internal = []
        self.redirects = []
        self.external_links_count = 0
        self.failed_requests = 0


# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────
def normalize_url(url):
    url, _ = urldefrag(url)
    return url.rstrip('/')


def fetch_sitemap(start_url):
    parsed = urlparse(start_url)
    sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    urls = []
    try:
        r = requests.get(sitemap_url, headers=HEADERS, timeout=8, verify=False)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "xml")
            for loc in soup.find_all("loc"):
                urls.append(normalize_url(loc.text.strip()))
    except:
        pass
    return urls


def js_render(url):
    if not JS_AVAILABLE:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            start = time.time()
            page.goto(url, timeout=20000)
            html = page.content()
            timing = page.evaluate("() => performance.timing")
            browser.close()
            return html, timing, time.time() - start
    except:
        return None


# ────────────────────────────────────────────────
# Main Crawl
# ────────────────────────────────────────────────
def perform_crawl(start_url: str, max_pages: int = 35) -> CrawlResult:

    if not start_url.startswith(('http://', 'https://')):
        start_url = 'https://' + start_url.lstrip('/')

    start_url = normalize_url(start_url.replace('http://', 'https://'))
    domain = urlparse(start_url).netloc

    visited = set()
    result = CrawlResult()

    # Sitemap-first crawl (non-breaking)
    sitemap_urls = fetch_sitemap(start_url)
    queue = deque(sitemap_urls if sitemap_urls else [start_url])

    while queue and len(visited) < max_pages:
        url = normalize_url(queue.popleft())
        if url in visited:
            continue
        visited.add(url)

        try:
            start_time = time.time()
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=(7, 20),
                allow_redirects=True,
                verify=False
            )
            load_time = time.time() - start_time

            result.status_counts[response.status_code] += 1

            if response.history:
                for r in response.history:
                    result.redirects.append((r.url, r.headers.get('Location')))

            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type:
                continue

            html = response.text
            timing_data = None

            # JS rendering fallback (SAFE)
            if JS_AVAILABLE and len(html) < 2000:
                js = js_render(url)
                if js:
                    html, timing_data, js_load = js

            soup = BeautifulSoup(html, 'lxml')

            # Lightweight Core Web Vitals (approx)
            core_web_vitals = {
                "ttfb_ms": int(response.elapsed.total_seconds() * 1000),
                "load_time_sec": round(load_time, 2),
                "js_rendered": bool(timing_data)
            }

            page_data = {
                "url": url,
                "status_code": response.status_code,
                "title": soup.title.string.strip() if soup.title and soup.title.string else None,
                "h1_tags": [h.get_text(strip=True) for h in soup.find_all('h1')],
                "meta_description": soup.find('meta', attrs={'name': 'description'})['content']
                    if soup.find('meta', attrs={'name': 'description'}) else None,
                "word_count": len(soup.get_text(separator=' ', strip=True).split()),
                "canonical": soup.find('link', rel='canonical')['href']
                    if soup.find('link', rel='canonical') else None,
                "robots_meta": soup.find('meta', attrs={'name': 'robots'})['content']
                    if soup.find('meta', attrs={'name': 'robots'}) else None,

                # ✅ ADDITIVE (non-breaking)
                "core_web_vitals": core_web_vitals
            }

            result.pages.append(page_data)

            for link in soup.find_all('a', href=True):
                href = normalize_url(urljoin(url, link['href']))
                parsed = urlparse(href)

                if parsed.scheme not in ('http', 'https'):
                    continue

                if parsed.netloc == domain or not parsed.netloc:
                    if href not in visited:
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
            result.failed_requests += 1
            result.status_counts[0] += 1
            result.broken_internal.append({
                "url": url,
                "error": str(e)[:120],
                "from": url
            })

    for page in result.pages:
        if page["status_code"] >= 400:
            result.broken_internal.append({
                "url": page["url"],
                "status": page["status_code"],
                "type": "http_error"
            })

    return result
