import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, defaultdict

# Disable SSL warnings for international compatibility with all sites
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {"User-Agent": "FFTechAuditor/1.0 (+https://fftech.ai)"}

class CrawlResult:
    def __init__(self):
        self.pages = [] # Changed to list of dicts for 200-metric flexibility
        self.status_counts = defaultdict(int)
        self.internal_links = defaultdict(list)
        self.external_links = defaultdict(list)
        self.broken_internal = []
        self.broken_external = []

def is_same_host(start_url: str, link: str) -> bool:
    return urlparse(start_url).netloc == urlparse(link).netloc

def perform_crawl(start_url: str, max_pages: int = 10, timeout: int = 5) -> 'CrawlResult':
    """
    Optimized Engine: Fixed SSL issues and reduced delay.
    """
    q = deque([start_url])
    seen = set()
    result = CrawlResult()
    
    # 1. Main Crawl Loop
    while q and len(seen) < max_pages:
        url = q.popleft()
        if url in seen: continue
        seen.add(url)
        
        try:
            # Added verify=False to prevent the SSL Halt
            r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True, verify=False)
            result.status_counts[r.status_code] += 1
            
            if 'text/html' in r.headers.get('Content-Type', ''):
                soup = BeautifulSoup(r.text, 'html.parser')
                
                # Store page data for SEO and 200-metric analysis
                result.pages.append({
                    "url": url,
                    "html": r.text,
                    "status_code": r.status_code,
                    "h1_tags": [h.text for h in soup.find_all('h1')],
                    "title": soup.title.string if soup.title else None,
                    "meta_description": soup.find('meta', attrs={'name': 'description'}).get('content') if soup.find('meta', attrs={'name': 'description'}) else None
                })

                for a in soup.find_all('a', href=True):
                    href = urljoin(url, a['href'])
                    if href.startswith('mailto:') or href.startswith('tel:'): continue
                    
                    if is_same_host(start_url, href):
                        result.internal_links[url].append(href)
                        if href not in seen: q.append(href)
                    else:
                        result.external_links[url].append(href)
                        
        except Exception:
            result.status_counts[0] += 1
            
    # 2. Optimized Link Check (The Delay Killer)
    # We only check a SMALL subset of internal links to keep the audit fast
    links_to_verify = set()
    for links in result.internal_links.values():
        for l in links:
            links_to_verify.add(l)
            if len(links_to_verify) > 20: break # STRICT LIMIT to prevent hanging
    
    for l in list(links_to_verify)[:20]:
        try:
            # verify=False is critical here too
            rr = requests.head(l, headers=HEADERS, timeout=3, allow_redirects=True, verify=False)
            if rr.status_code >= 400:
                result.broken_internal.append((l, rr.status_code))
        except Exception:
            pass

    return result

def crawl_site(start_url: str, max_pages: int = 10):
    """
    Summarized wrapper for SEO scores.
    """
    result_obj = perform_crawl(start_url, max_pages)
    
    # Analyze the first page (usually Home)
    onpage = {"missing_title_tags": 0, "missing_meta_descriptions": 0, "multiple_h1": 0}
    if result_obj.pages:
        home = result_obj.pages[0]
        if not home["title"]: onpage["missing_title_tags"] = 1
        if not home["meta_description"]: onpage["missing_meta_descriptions"] = 1
        if len(home["h1_tags"]) > 1: onpage["multiple_h1"] = 1

    return {
        "pages_crawled": len(result_obj.pages),
        "onpage_stats": onpage,
        "broken_internal_count": len(result_obj.broken_internal),
        "status_codes": dict(result_obj.status_counts)
    }
