# app/audit/psi.py
import aiohttp
import asyncio

async def fetch_lighthouse(url: str, api_key: str, strategy: str = "desktop") -> dict:
    """
    Fetch Lighthouse / PageSpeed Insights data asynchronously.
    strategy: "desktop" or "mobile"
    Returns: dict with lcp_ms, fcp_ms, total_page_size_kb
    """
    if not api_key:
        return {}

    endpoint = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={api_key}&strategy={strategy}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, timeout=20) as response:
                data = await response.json()

                audits = data.get("lighthouseResult", {}).get("audits", {})

                lcp = int(audits.get("largest-contentful-paint", {}).get("numericValue", 0))
                fcp = int(audits.get("first-contentful-paint", {}).get("numericValue", 0))
                total_size = int(audits.get("total-byte-weight", {}).get("numericValue", 0) / 1024)

                return {
                    "lcp_ms": lcp,
                    "fcp_ms": fcp,
                    "total_page_size_kb": total_size
                }
    except Exception as e:
        print(f"Lighthouse fetch error for {url} ({strategy}): {e}")
        return {}
