"""
High‑performance asynchronous link analysis module.

This version maintains FULL backward compatibility with the original:
- Same function name
- Same arguments
- Same callback events
- Same output dict structure
- Same broken‑link detection rules
- Same internal/external domain logic
- Same concurrency & limits
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Any, Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag


async def analyze_links_async(
    html_dict: Dict[str, str],
    base_url: str,
    callback: Any = None
) -> Dict[str, Any]:
    """
    Analyze internal/external links and detect broken internal URLs.

    Returns example:
    {
        "internal_links_count": int,
        "external_links_count": int,
        "broken_internal_links": int,
        "broken_links_list": list[str]
    }
    """

    html = html_dict.get(base_url, "")

    # Handle missing HTML
    if not html:
        if callback:
            await callback({
                "status": "No HTML content received",
                "crawl_progress": 70
            })
        return {
            "internal_links_count": 0,
            "external_links_count": 0,
            "broken_internal_links": 0,
            "broken_links_list": []
        }

    # Parse HTML safely
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # Find all anchor tags
    link_tags: List[Tag] = soup.find_all("a", href=True)
    total_links = len(link_tags)

    if callback:
        await callback({
            "status": f"Found {total_links} potential links – analyzing...",
            "crawl_progress": 65
        })

    # Normalize domain
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc.lower()
    if base_domain.startswith("www."):
        base_domain = base_domain[4:]

    internal: Set[str] = set()
    external: Set[str] = set()
    to_check: List[str] = []

    # =====================================================
    #  CLASSIFY LINKS
    # =====================================================
    for tag in link_tags:
        href = tag["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue

        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        if domain == base_domain:
            internal.add(full_url)
            to_check.append(full_url)
        else:
            external.add(full_url)

    # =====================================================
    #  BROKEN LINK VALIDATION (Concurrent)
    # =====================================================
    broken: List[str] = []

    if to_check:
        if callback:
            await callback({
                "status": f"Validating {min(len(to_check), 50)} internal links...",
                "crawl_progress": 75
            })

        semaphore = asyncio.Semaphore(20)

        async def check_one(url: str) -> None:
            async with semaphore:
                try:
                    async with httpx.AsyncClient(
                        timeout=4.0, follow_redirects=True
                    ) as client:
                        response = await client.head(url)
                        if response.status_code >= 400:
                            broken.append(url)
                except Exception:
                    broken.append(url)

        # Only validate first 50
        tasks = [check_one(url) for url in to_check[:50]]
        await asyncio.gather(*tasks, return_exceptions=True)

    # =====================================================
    #  FINAL RESULT
    #  (STRUCTURE MUST REMAIN UNCHANGED)
    # =====================================================

    result = {
        "internal_links_count": len(internal),
        "external_links_count": len(external),
        "broken_internal_links": len(broken),
        "broken_links_list": broken[:10]
    }

    if callback:
        await callback({
            "status": (
                f"Links analyzed: "
                f"{len(internal)} internal, "
                f"{len(external)} external, "
                f"{len(broken)} broken"
            ),
            "crawl_progress": 95
        })

    return result
