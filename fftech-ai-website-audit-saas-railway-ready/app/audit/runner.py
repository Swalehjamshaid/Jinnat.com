# app/audit/runner.py

import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import re

# -------------------------------------------
# Global Configuration
# -------------------------------------------
MAX_CONCURRENT_REQUESTS = 10
TIMEOUT = 10

# -------------------------------------------
# Helper functions
# -------------------------------------------

async def fetch(session: aiohttp.ClientSession, url: str) -> str:
    """Fetch HTML content asynchronously with timeout."""
    try:
        async with session.get(url, timeout=TIMEOUT) as response:
            return await response.text(), str(response.status)
    except Exception:
        return "", "error"

def normalize_url(base: str, link: str) -> str:
    """Normalize relative and absolute URLs."""
    if not link:
        return ""
    parsed = urlparse(link)
    if parsed.scheme in ["http", "https"]:
        return link
    return urljoin(base, link)

def extract_links(html: str, base_url: str) -> tuple[list[str], list[str]]:
    """Return internal and external links separately."""
    soup = BeautifulSoup(html, "html.parser")
    internal = set()
    external = set()

    for a in soup.find_all("a", href=True):
        href = normalize_url(base_url, a['href'])
        if urlparse(href).netloc == urlparse(base_url).netloc:
            internal.add(href)
        else:
            external.add(href)

    return list(internal), list(external)

def analyze_seo(html: str) -> dict:
    """Check SEO and accessibility features."""
    soup = BeautifulSoup(html, "html.parser")
    images_missing_alt = sum(1 for img in soup.find_all("img") if not img.get("alt"))
    titles_missing = 0 if soup.title and soup.title.string else 1
    meta_description_missing = 1 if not soup.find("meta", attrs={"name": "description"}) else 0

    return {
        "images_missing_alt": images_missing_alt,
        "titles_missing": titles_missing,
        "meta_description_missing": meta_description_missing
    }

async def audit_page(session: aiohttp.ClientSession, url: str) -> dict:
    """Audit a single page for links and SEO."""
    html, status = await fetch(session, url)
    if status != "200":
        return {
            "url": url,
            "status": status,
            "internal_links": [],
            "external_links": [],
            "broken_links": [],
            "seo": {}
        }

    internal_links, external_links = extract_links(html, url)
    seo = analyze_seo(html)

    # Check broken internal links concurrently
    broken = []
    tasks = []
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def check_link(link):
        async with semaphore:
            _, link_status = await fetch(session, link)
            if link_status != "200":
                broken.append(link)

    for link in internal_links:
        tasks.append(asyncio.create_task(check_link(link)))

    await asyncio.gather(*tasks)

    return {
        "url": url,
        "status": status,
        "internal_links": internal_links,
        "external_links": external_links,
        "broken_links": broken,
        "seo": seo
    }

# -------------------------------------------
# Main Audit Runner
# -------------------------------------------

def run_audit(start_url: str) -> dict:
    """World-class async audit runner returning a detailed report."""

    async def crawl():
        visited = set()
        to_visit = [start_url]
        report = []

        async with aiohttp.ClientSession() as session:
            while to_visit:
                url = to_visit.pop(0)
                if url in visited:
                    continue
                visited.add(url)

                page_report = await audit_page(session, url)
                report.append(page_report)

                # Add new internal links to queue
                for link in page_report["internal_links"]:
                    if link not in visited:
                        to_visit.append(link)

        # Aggregate results
        total_pages = len(report)
        total_internal_links = sum(len(r["internal_links"]) for r in report)
        total_external_links = sum(len(r["external_links"]) for r in report)
        total_broken_links = sum(len(r["broken_links"]) for r in report)
        total_images_missing_alt = sum(r["seo"]["images_missing_alt"] for r in report)
        total_titles_missing = sum(r["seo"]["titles_missing"] for r in report)
        total_meta_missing = sum(r["seo"]["meta_description_missing"] for r in report)

        return {
            "total_pages": total_pages,
            "total_internal_links": total_internal_links,
            "total_external_links": total_external_links,
            "total_broken_links": total_broken_links,
            "total_images_missing_alt": total_images_missing_alt,
            "total_titles_missing": total_titles_missing,
            "total_meta_missing": total_meta_missing,
            "page_details": report
        }

    return asyncio.run(crawl())
