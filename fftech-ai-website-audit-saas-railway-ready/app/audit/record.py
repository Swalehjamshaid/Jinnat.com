# app/audit/record.py
import aiohttp
import asyncio
from typing import Dict

async def fetch_site_html(url: str) -> Dict[str, str]:
    """
    Fetch HTML content of a website asynchronously.
    Ignores SSL errors to prevent certificate issues.
    """
    html_docs = {}
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout, connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0 (FFTech AI Auditor)"}) as response:
                html_docs[url] = await response.text()
    except Exception as e:
        print(f"Error fetching HTML for {url}: {e}")
        html_docs[url] = ""
    return html_docs
