import requests
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, defaultdict

# Import the grading logic to assign A, B, C, etc.
from .grader import to_grade

HEADERS = {"User-Agent": "FFTechAuditor/1.0 (+https://fftech.ai)"}

class CrawlResult:
    def __init__(self):
        self.pages = {}
        self.status_counts = defaultdict(int)
        self.internal_links = defaultdict(list)
        self.external_links = defaultdict(list)
        self.broken_internal = []
        self.broken_external = []

def is_same_host(start_url: str, link: str) -> bool:
    return urlparse(start_url).netloc == urlparse(link).netloc

def crawl(start_url: str, max_pages: int = 10, timeout: int = 10) -> 'CrawlResult':
    """
    Synchronous crawling logic with broken link detection.
    """
    q = deque([start_url])
    seen = set()
    result = CrawlResult()
    
    # 1. Primary Crawl Loop
    while q and len(seen) < max_pages:
        url = q.popleft()
        if url in seen:
            continue
        seen.add(url)
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            result.status_counts[r.status_code] += 1
            
            # If the page is broken, track it
            if r.status_code >= 400:
                result.broken_internal.append(url)
                continue

            if 'text/html' in r.headers.get('Content-Type', ''):
                soup = BeautifulSoup(r.text, 'html.parser')
                result.pages[url] = r.text
                for a in soup.find_all('a', href=True):
                    href = urljoin(url, a['href'])
                    
                    if href.startswith('mailto:') or href.startswith('tel:'):
                        continue
                    
                    if is_same_host(start_url, href):
                        result.internal_links[url].append(href)
                        if href not in seen:
                            q.append(href)
                    else:
                        result.external_links[url].append(href)
        except requests.RequestException:
            result.status_counts[0] += 1
            result.broken_internal.append(url)
            
    return result

# --- ASYNC BRIDGE: The Router calls this ---
async def analyze(url: str):
    """
    Asynchronous bridge for the FastAPI Router.
    Runs the crawl and returns formatted data for the DB and PDF.
    """
    # Run the synchronous crawl in a thread pool to avoid blocking FastAPI
    loop = asyncio.get_event_loop()
    crawl_data = await loop.run_in_executor(None, crawl, url)
    
    # Calculate scores based on crawl data
    total_pages = len(crawl_data.pages)
    # We count broken links identified during the crawl
    broken_links = len(crawl_data.broken_internal)
    
    # Basic scoring logic
    seo_score = max(40, 100 - (broken_links * 15))
    perf_score = 75  # Placeholder for speed test
    sec_score = 85   # Placeholder for header checks
    
    overall = int((seo_score + perf_score + sec_score) / 3)
    grade = to_grade(overall)

    return {
        "url": url,
        "overall_score": overall,
        "grade": grade,
        "category_scores": {
            "SEO": seo_score,
            "Performance": perf_score,
            "Security": sec_score
        },
        "metrics": {
            "pages_crawled": total_pages,
            "broken_links": broken_links,
            "status_200": crawl_data.status_counts[200]
        },
        "summary": {
            "executive_summary": f"Analyzed {total_pages} pages for {url}.",
            "strengths": ["Site architecture is crawlable" if total_pages > 1 else "Landing page active"],
            "weaknesses": [f"Found {broken_links} broken links" if broken_links > 0 else "Low page count"],
            "priority_fixes": ["Repair broken URLs" if broken_links > 0 else "Increase content depth"]
        }
    }
