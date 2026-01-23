import requests
import urllib3
import time
import json
import random
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
from collections import deque, defaultdict
from requests.exceptions import RequestException, Timeout, SSLError
from urllib.robotparser import RobotFileParser

# Optional JS rendering (requires: pip install playwright)
try:
    from playwright.sync_api import sync_playwright
    JS_AVAILABLE = True
except ImportError:
    JS_AVAILABLE = False

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
]

class CrawlResult:
    def __init__(self):
        self.pages = []
        self.summary = {
            "total_pages_crawled": 0,
            "status_codes": defaultdict(int),
            "broken_links": [],
            "redirects": [],
            "external_links_count": 0,
            "failed_requests": 0,
            "health_score": 100  # will be adjusted
        }

    def add_page(self, page_data):
        self.pages.append(page_data)
        self.summary["total_pages_crawled"] += 1
        self.summary["status_codes"][page_data["status_code"]] += 1

    def to_json(self, filename="website_audit.json"):
        data = {
            "summary": self.summary,
            "pages": self.pages,
            "broken_links": self.summary["broken_links"],
            "redirects": self.summary["redirects"],
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Audit saved to {filename} | Pages: {len(self.pages)} | Broken: {len(self.summary['broken_links'])}")

def normalize_url(url):
    url, _ = urldefrag(url)
    return url.rstrip('/')

def fetch_robots_txt(base_url):
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        resp = requests.get(robots_url, timeout=6)
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
            return rp
    except:
        pass
    return None

def fetch_sitemap(start_url):
    parsed = urlparse(start_url)
    sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    urls = []
    try:
        r = requests.get(sitemap_url, timeout=8)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "xml")
            for loc in soup.find_all("loc"):
                urls.append(normalize_url(loc.text.strip()))
    except:
        pass
    return urls

def js_render(url):
    if not JS_AVAILABLE:
        return None, None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            html = page.content()
            # Approximate performance timing
            perf = page.evaluate("() => JSON.stringify(performance.timing)")
            browser.close()
            return html, json.loads(perf)
    except Exception as e:
        print(f"JS render failed for {url}: {e}")
        return None, None

def perform_crawl(
    start_url: str,
    max_pages: int = 50,
    max_depth: int = 6,
    respect_robots: bool = True,
    use_js_fallback: bool = True,
    delay_range: tuple = (0.8, 2.2)
) -> CrawlResult:
    if not start_url.startswith(('http://', 'https://')):
        start_url = 'https://' + start_url.lstrip('/')
    start_url = normalize_url(start_url.replace('http://', 'https://'))

    domain = urlparse(start_url).netloc
    result = CrawlResult()
    visited = set()
    queue = deque([(start_url, 0)])  # (url, depth)

    robots_parser = fetch_robots_txt(start_url) if respect_robots else None

    # Prefer sitemap if available
    sitemap_urls = fetch_sitemap(start_url)
    if sitemap_urls:
        queue = deque([(u, 0) for u in sitemap_urls if u.startswith(f"https://{domain}")][:max_pages])

    while queue and len(visited) < max_pages:
        url, depth = queue.popleft()
        if url in visited or depth > max_depth:
            continue

        if robots_parser and not robots_parser.can_fetch("*", url):
            continue  # Skip disallowed by robots.txt

        visited.add(url)
        time.sleep(random.uniform(*delay_range))  # Polite random delay

        headers = {"User-Agent": random.choice(USER_AGENTS)}

        try:
            start_time = time.time()
            response = requests.get(
                url, headers=headers, timeout=(8, 25), allow_redirects=True, verify=False
            )
            load_time = time.time() - start_time
            status = response.status_code
            result.summary["status_codes"][status] += 1

            if response.history:
                for hist in response.history:
                    result.summary["redirects"].append({
                        "from": hist.url,
                        "to": hist.headers.get('Location'),
                        "code": hist.status_code
                    })

            if status >= 400:
                result.summary["broken_links"].append({"url": url, "status": status, "type": "http_error"})
                continue

            if 'text/html' not in response.headers.get('Content-Type', '').lower():
                continue

            html = response.text
            js_perf = None
            if use_js_fallback and JS_AVAILABLE and len(html.strip()) < 3000:  # Likely JS-heavy
                html_js, perf = js_render(url)
                if html_js:
                    html = html_js
                    js_perf = perf

            soup = BeautifulSoup(html, 'lxml')

            # Extract key meta & on-page
            title = soup.title.string.strip() if soup.title else None
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            meta_desc = meta_desc['content'].strip() if meta_desc else None

            # Headings
            headings = {}
            for level in range(1, 7):
                tags = soup.find_all(f'h{level}')
                headings[f'h{level}'] = [t.get_text(strip=True) for t in tags if t.get_text(strip=True)]

            # Images
            images = soup.find_all('img')
            img_count = len(images)
            img_with_alt = sum(1 for img in images if img.get('alt') and img['alt'].strip())

            # Security headers
            sec_headers = {
                "strict_transport_security": response.headers.get('Strict-Transport-Security'),
                "content_security_policy": response.headers.get('Content-Security-Policy'),
                "x_frame_options": response.headers.get('X-Frame-Options'),
                "x_content_type_options": response.headers.get('X-Content-Type-Options'),
            }

            # Structured data
            json_ld = soup.find_all('script', type='application/ld+json')
            structured_data_count = len(json_ld)

            # Open Graph / Twitter
            og_title = soup.find('meta', property='og:title')['content'] if soup.find('meta', property='og:title') else None
            og_desc = soup.find('meta', property='og:description')['content'] if soup.find('meta', property='og:description') else None

            # Viewport for mobile hint
            viewport = soup.find('meta', attrs={'name': 'viewport'})

            core_vitals = {
                "ttfb_ms": int(response.elapsed.total_seconds() * 1000),
                "load_time_sec": round(load_time, 2),
                "js_rendered": bool(js_perf),
                "dom_load_ms": js_perf.get('domContentLoadedEventEnd', 0) - js_perf.get('navigationStart', 0) if js_perf else None,
            }

            page_data = {
                "url": url,
                "status_code": status,
                "title": title,
                "meta_description": meta_desc,
                "word_count": len(soup.get_text(separator=' ', strip=True).split()),
                "canonical": soup.find('link', rel='canonical')['href'] if soup.find('link', rel='canonical') else url,
                "robots_meta": soup.find('meta', attrs={'name': 'robots'})['content'] if soup.find('meta', attrs={'name': 'robots'}) else None,
                "headings": headings,
                "images": {"total": img_count, "with_alt": img_with_alt},
                "structured_data_count": structured_data_count,
                "og_title": og_title,
                "og_desc": og_desc,
                "viewport_meta": viewport['content'] if viewport else None,
                "security_headers": {k: v for k, v in sec_headers.items() if v},
                "core_web_vitals": core_vitals
            }
            result.add_page(page_data)

            # Enqueue internal links
            for a in soup.find_all('a', href=True):
                href = normalize_url(urljoin(url, a['href']))
                parsed = urlparse(href)
                if parsed.scheme not in ('http', 'https'):
                    continue
                if parsed.netloc == domain or not parsed.netloc:
                    if href not in visited:
                        queue.append((href, depth + 1))
                else:
                    result.summary["external_links_count"] += 1

        except Timeout:
            result.summary["failed_requests"] += 1
            result.summary["broken_links"].append({"url": url, "type": "timeout"})
        except SSLError:
            result.summary["failed_requests"] += 1
            result.summary["broken_links"].append({"url": url, "type": "ssl_error"})
        except RequestException as e:
            result.summary["failed_requests"] += 1
            result.summary["broken_links"].append({"url": url, "type": "request_error", "error": str(e)[:150]})

    # Final health score approximation (simple: % non-2xx + broken ratio)
    total = result.summary["total_pages_crawled"] or 1
    bad = sum(v for k, v in result.summary["status_codes"].items() if k >= 400 or k == 0)
    result.summary["health_score"] = max(0, 100 - int((bad + result.summary["failed_requests"]) / total * 100))

    return result


# ────────────────────────────────────────────────
# Example usage
# ────────────────────────────────────────────────
if __name__ == "__main__":
    url = "https://example.com"  # ← CHANGE THIS
    result = perform_crawl(
        url,
        max_pages=60,
        max_depth=5,
        respect_robots=True,
        use_js_fallback=JS_AVAILABLE,
        delay_range=(1.0, 3.0)
    )
    result.to_json()
