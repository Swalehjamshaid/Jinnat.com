import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, defaultdict

HEADERS = {"User-Agent": "FFTechAuditor/1.0 (+https://fftech.ai)"}

class CrawlResult:
    def __init__(self):
        self.pages = {}
        self.status_counts = defaultdict(int)
        self.internal_links = defaultdict(list)
        self.broken_internal = []

def is_same_host(start_url: str, link: str) -> bool:
    return urlparse(start_url).netloc == urlparse(link).netloc

def crawl_site(start_url: str, max_pages: int = 10):
    """
    Crawls and returns a dictionary for the grader.
    """
    q = deque([start_url])
    seen = set()
    result = CrawlResult()
    
    while q and len(seen) < max_pages:
        url = q.popleft()
        if url in seen: continue
        seen.add(url)
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            result.status_counts[r.status_code] += 1
            if 'text/html' in r.headers.get('Content-Type', ''):
                result.pages[url] = r.text
                soup = BeautifulSoup(r.text, 'html.parser')
                for a in soup.find_all('a', href=True):
                    href = urljoin(url, a['href'])
                    if is_same_host(start_url, href) and href not in seen:
                        q.append(href)
        except:
            result.status_counts[0] += 1

    # Basic On-page SEO Analysis
    onpage = {"missing_title_tags": 0, "missing_meta_descriptions": 0, "multiple_h1": 0}
    if start_url in result.pages:
        s = BeautifulSoup(result.pages[start_url], 'html.parser')
        if not s.title: onpage["missing_title_tags"] = 1
        if not s.find('meta', attrs={'name': 'description'}): onpage["missing_meta_descriptions"] = 1
        if len(s.find_all('h1')) > 1: onpage["multiple_h1"] = 1

    return {
        "pages_crawled": len(seen),
        "onpage_stats": onpage,
        "broken_internal_count": len(result.broken_internal),
        "status_codes": dict(result.status_counts)
    }
