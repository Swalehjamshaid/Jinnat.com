import time
import requests
from urllib.parse import urljoin, urlparse
from collections import defaultdict, deque
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'FFTechAuditor/2.0 (+https://yourdomain.com)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

JUNK_EXTENSIONS = (
    '.pdf', '.jpg', '.png', '.jpeg', '.gif', '.webp', '.svg', '.zip',
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.mp3', '.mp4'
)

class CrawlResult:
    def __init__(self):
        self.pages = {}
        self.status_counts = defaultdict(int)
        self.internal_links = defaultdict(list)
        self.external_links = defaultdict(list)
        self.broken_internal = []
        self.total_crawl_time = 0
        self.crawled_count = 0

def should_crawl(url: str):
    return not any(url.lower().endswith(ext) for ext in JUNK_EXTENSIONS)

def is_same_host(start_url: str, link: str):
    return urlparse(start_url).netloc == urlparse(link).netloc

def crawl(start_url: str, max_pages=20, delay=0.4):
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
            resp = session.get(url, timeout=10)
            result.status_counts[resp.status_code] += 1
            if resp.status_code != 200:
                continue
            html = resp.text
            result.pages[url] = html
            soup = BeautifulSoup(html, "html.parser")
            for a_tag in soup.find_all("a", href=True):
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
        except Exception as e:
            result.status_counts[0] += 1
        time.sleep(delay)

    # Check broken internal links
    for from_url, links in result.internal_links.items():
        for to_url in links:
            if to_url in result.pages:
                continue
            try:
                r = session.head(to_url, timeout=5)
                if r.status_code >= 400:
                    result.broken_internal.append((from_url, to_url, r.status_code))
            except:
                result.broken_internal.append((from_url, to_url, 0))

    result.total_crawl_time = round(time.time() - start_time, 2)
    return result
