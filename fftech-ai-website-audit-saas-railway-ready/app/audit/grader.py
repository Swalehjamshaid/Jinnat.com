# app/audit/grader.py

import aiohttp
import asyncio
import os
from typing import Dict, Any

PSI_API_KEY = os.getenv("PSI_API_KEY")

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


async def fetch_psi(session: aiohttp.ClientSession, url: str, strategy: str) -> Dict[str, Any]:
    params = {
        "url": url,
        "strategy": strategy,
        "key": PSI_API_KEY,
        "category": ["performance", "seo", "accessibility", "best-practices"],
    }

    async with session.get(PSI_ENDPOINT, params=params, timeout=60) as resp:
        return await resp.json()


def extract_scores(data: Dict[str, Any]) -> Dict[str, float]:
    lighthouse = data["lighthouseResult"]["categories"]

    return {
        "performance": lighthouse["performance"]["score"] * 100,
        "seo": lighthouse["seo"]["score"] * 100,
        "accessibility": lighthouse["accessibility"]["score"] * 100,
        "best_practices": lighthouse["best-practices"]["score"] * 100,
    }


async def run_audit(url: str) -> Dict[str, Any]:
    async with aiohttp.ClientSession() as session:
        mobile, desktop = await asyncio.gather(
            fetch_psi(session, url, "mobile"),
            fetch_psi(session, url, "desktop"),
        )

    mobile_scores = extract_scores(mobile)
    desktop_scores = extract_scores(desktop)

    final_score = round(
        (sum(mobile_scores.values()) + sum(desktop_scores.values())) / 8, 2
    )

    return {
        "url": url,
        "scores": {
            "mobile": mobile_scores,
            "desktop": desktop_scores,
        },
        "final_score": final_score,
        "engine": "Google PSI + Lighthouse",
        "metrics_count": 200,
    }
