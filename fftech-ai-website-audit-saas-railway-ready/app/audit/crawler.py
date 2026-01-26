# fftech-ai-website-audit-saas-railway-ready/app/audit/crawler.py

import asyncio
import logging
from urllib.parse import urlparse, urljoin
from typing import Dict, List
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("audit_engine")

# -------------------------
# Configurable Settings
# -------------------------
MAX_PAGES = 20        # Maximum pages to crawl
CONCURRENCY = 10      # Number of parallel requests
TIMEOUT = 5.0         # HTTP request timeout

# -------------------------
# Helper: Fetch single page
# -------------------------
async def fetch_page(client: httpx.AsyncClient, url: str):
    try:
        resp = await client.get(url, timeout=TIMEOUT)
        return resp.text, resp.status_code
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return "", 0

# -------------------------
# Helper: Analyze page for SEO basics
# -------------------------
def analyze_page_seo(html: str, url: str):
    soup = BeautifulSoup(html, "lxml")
    seo_score = 100
    issues = []

    # Check title
    title = soup.title.string.strip() if soup.title else ""
    if not title:
        seo_score -= 10
        issues.append("Missing title tag")

    # Check meta description
    desc = soup.find("meta", attrs={"name":"description"})
    if not desc or not desc.get("content", "").strip():
        seo_score -= 10
        issues.append("Missing meta description")

    # Check H1 tags
    h1 = soup.find_all("h1")
    if not h1:
        seo_score -= 5
        issues.append("Missing H1 tag")

    # Check images alt
    imgs = soup.find_all("img")
    for img in imgs:
        if not img.get("alt"):
            seo_score -= 1
            issues.append(f"Image missing alt on {url}")

    # Extract internal & external links
    internal_links = set()
    external_links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        parsed_href = urlparse(href)
        if parsed_href.netloc == "" or parsed_href.netloc == urlparse(url).netloc:
            full_url = urljoin(url, href)
            internal_links.add(full_url)
        else:
            external_links.add(href)

    return {
        "seo_score": max(seo_score, 0),
        "issues": issues,
        "internal_links": list(internal_links),
        "external_links": list(external_links),
    }

# -------------------------
# Main Crawler Function
# -------------------------
async def crawl(start_url: str, max_pages: int = MAX_PAGES):
    domain = urlparse(start_url).netloc
    visited = {start_url}
    to_crawl = [start_url]
    results = []

    limits = httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=5)
    async with httpx.AsyncClient(verify=False, limits=limits, follow_redirects=True) as client:
        while to_crawl and len(results) < max_pages:
            batch = to_crawl[:CONCURRENCY]
            to_crawl = to_crawl[CONCURRENCY:]

            tasks = [fetch_page(client, url) for url in batch]
            responses = await asyncio.gather(*tasks)

            new_links = []
            for i, (html, status) in enumerate(responses):
                url = batch[i]

                if status != 200:
                    logger.info(f"Broken page: {url} (status {status})")
                    results.append({
                        "url": url,
                        "title": "N/A",
                        "html": "",
                        "seo": {},
                        "broken": True
                    })
                    continue

                seo_data = analyze_page_seo(html, url)
                results.append({
                    "url": url,
                    "title": seo_data.get("title", BeautifulSoup(html,"lxml").title.string if BeautifulSoup(html,"lxml").title else "N/A"),
                    "html": html,
                    "seo": seo_data,
                    "broken": False
                })

                # Add internal links to crawl
                for link in seo_data["internal_links"]:
                    if link not in visited and len(visited) < max_pages:
                        visited.add(link)
                        new_links.append(link)

            to_crawl.extend(new_links)

    return {"report": results}

