import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, defaultdict

# Disable SSL warnings for international compatibility (Fixes Haier.com.pk issue)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
HEADERS = {"User-Agent": "FFTechAuditor/1.0 (+https://fftech.ai)"}

class CrawlResult:
    def __init__(self):
        self.pages = []
        self.status_counts = defaultdict(int)
        self.internal_links = defaultdict(list)
        self.broken_internal = []

def perform_crawl(start_url: str, max_pages: int = 10) -> 'CrawlResult':
    q = deque([start_url])
    seen = set()
    result = CrawlResult()
    
    while q and len(seen) < max_pages:
        url = q.popleft()
        if url in seen: continue
        seen.add(url)
        try:
            # verify=False prevents SSL-related delays and crashes
            r = requests.get(url, headers=HEADERS, timeout=10, verify=False)
            result.status_counts[r.status_code] += 1
            if 'text/html' in r.headers.get('Content-Type', ''):
                soup = BeautifulSoup(r.text, 'html.parser')
                result.pages.append({
                    "url": url, 
                    "html": r.text, 
                    "status_code": r.status_code,
                    "title": soup.title.string.strip() if soup.title and soup.title.string else None,
                    "h1_tags": [h.get_text().strip() for h in soup.find_all('h1')],
                    "meta": soup.find('meta', attrs={'name': 'description'}).get('content') if soup.find('meta', attrs={'name': 'description'}) else None
                })
                for a in soup.find_all('a', href=True):
                    href = urljoin(url, a['href'])
                    if urlparse(start_url).netloc == urlparse(href).netloc:
                        result.internal_links[url].append(href)
                        if href not in seen: q.append(href)
        except:
            result.status_counts[0] += 1
    return result
