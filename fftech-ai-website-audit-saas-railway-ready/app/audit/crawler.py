# app/audit/crawler.py
import asyncio
import time
from urllib.request import urlopen, Request
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser
from collections import defaultdict

JUNK_EXTENSIONS = ('.pdf', '.jpg', '.png', '.zip', '.docx', '.jpeg', '.gif')
HEADERS = {'User-Agent': 'FFTechAuditor/2.0'}

class SimpleHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

class CrawlResult:
    def __init__(self):
        self.pages = {}
        self.status_counts = defaultdict(int)
        self.internal_links = defaultdict(list)
        self.external_links = defaultdict(list)
        self.broken_internal = []
        self.total_crawl_time = 0

def is_same_host(start_url, link):
    return urlparse(start_url).netloc == urlparse(link).netloc

async def crawl(start_url: str, max_pages=15, timeout=5):
    start_time = time.time()
    result = CrawlResult()
    queue = [start_url]
    seen = set()

    while queue and len(seen) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)

        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=timeout) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                status = resp.getcode()
                result.status_counts[status] += 1
                result.pages[url] = html

                parser = SimpleHTMLParser()
                parser.feed(html)
                for href in parser.links:
                    if any(href.lower().endswith(ext) for ext in JUNK_EXTENSIONS):
                        continue
                    abs_url = urljoin(url, href)
                    if is_same_host(start_url, abs_url):
                        result.internal_links[url].append(abs_url)
                        if abs_url not in seen:
                            queue.append(abs_url)
                    else:
                        result.external_links[url].append(abs_url)
        except Exception:
            result.status_counts[0] += 1

    result.total_crawl_time = round(time.time() - start_time, 2)
    return result
