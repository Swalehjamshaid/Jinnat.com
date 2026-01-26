# fftech-ai-website-audit-saas-railway-ready/app/audit/seo.py

from bs4 import BeautifulSoup
from typing import Dict
import httpx
import asyncio
import logging

logger = logging.getLogger("audit_engine")


async def analyze_onpage(html_docs: Dict[str, str], progress_callback=None) -> Dict[str, int]:
    """Analyze on-page SEO asynchronously."""
    metrics = {
        'missing_title': 0,
        'missing_meta_description': 0,
        'missing_h1': 0,
        'images_missing_alt': 0,
        'broken_links': 0,
    }

    async def check_link(client, url):
        try:
            resp = await client.head(url, timeout=5, follow_redirects=True)
            if resp.status_code >= 400:
                metrics['broken_links'] += 1
        except Exception:
            metrics['broken_links'] += 1

    async with httpx.AsyncClient() as client:
        for i, (url, html) in enumerate(html_docs.items(), start=1):
            soup = BeautifulSoup(html, 'lxml')

            if not soup.title or not (soup.title.string or '').strip():
                metrics['missing_title'] += 1

            if not soup.find('meta', attrs={'name': 'description'}):
                metrics['missing_meta_description'] += 1

            if not soup.find('h1'):
                metrics['missing_h1'] += 1

            metrics['images_missing_alt'] += sum(1 for img in soup.find_all('img') if not img.get('alt'))

            # Check links async
            tasks = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('http'):
                    tasks.append(check_link(client, href))
            if tasks:
                await asyncio.gather(*tasks)

            if progress_callback:
                await progress_callback({
                    "crawl_progress": round(i / len(html_docs) * 100, 2),
                    "status": f"Analyzed on-page SEO {i}/{len(html_docs)} pages…",
                    "finished": False
                })

    if progress_callback:
        await progress_callback({
            "crawl_progress": 100,
            "status": "On-page SEO analysis complete",
            "finished": True
        })

    return metrics
