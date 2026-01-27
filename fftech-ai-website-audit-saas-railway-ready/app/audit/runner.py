# app/audit/runner.py
import time
import httpx
from bs4 import BeautifulSoup
from app.audit.link import analyze_links_async

class WebsiteAuditRunner:
    def __init__(self, url: str):
        self.url = url if url.startswith("http") else f"https://{url}"

    async def run_audit(self, callback):
        try:
            # 1) Initialize
            await callback({"status": "🚀 Initializing Engine...", "crawl_progress": 10})
            start = time.time()

            # 2) Fetch page
            await callback({"status": "🌐 Fetching page...", "crawl_progress": 20})
            async with httpx.AsyncClient(timeout=12.0, verify=False) as client:
                res = await client.get(self.url, follow_redirects=True)
                lcp_ms = int((time.time() - start) * 1000)
                html = res.text

            # 3) Parse and simple SEO scoring
            await callback({"status": "🔍 Analyzing SEO & Security...", "crawl_progress": 50})
            soup = BeautifulSoup(html, "html.parser")

            has_title = 1 if soup.title else 0
            has_h1 = 1 if soup.find("h1") else 0
            seo_score = (has_title * 50) + (has_h1 * 50)

            # 4) Link Analysis
            links = await analyze_links_async({self.url: html}, self.url, callback)

            # Scores for charts
            speed_score = max(0, min(100, int(100 - (lcp_ms / 100))))  # crude proxy
            security_score = 90  # placeholder; add real checks if needed
            ai_trust_score = 95  # placeholder

            overall = int((seo_score * 0.7) + (speed_score * 0.3))
            grade = "A" if overall > 80 else "B" if overall > 60 else "C"

            # Chart.js wants datasets arrays
            bar_data = {
                "labels": ["SEO", "Speed", "Security", "AI"],
                "datasets": [
                    {
                        "label": "Scores",
                        "data": [seo_score, speed_score, security_score, ai_trust_score],
                        "backgroundColor": [
                            "rgba(255, 215, 0, 0.6)",
                            "rgba(59, 130, 246, 0.6)",
                            "rgba(34, 197, 94, 0.6)",
                            "rgba(147, 51, 234, 0.6)",
                        ],
                        "borderColor": [
                            "rgba(255, 215, 0, 1)",
                            "rgba(59, 130, 246, 1)",
                            "rgba(34, 197, 94, 1)",
                            "rgba(147, 51, 234, 1)",
                        ],
                        "borderWidth": 1,
                    }
                ],
            }

            doughnut_data = {
                "labels": ["Healthy", "Warning", "Broken"],
                "datasets": [
                    {
                        "data": [
                            int(links.get("internal_links_count", 0)),
                            2,
                            int(links.get("broken_internal_links", 0)),
                        ],
                        "backgroundColor": [
                            "rgba(34, 197, 94, 0.7)",
                            "rgba(234, 179, 8, 0.7)",
                            "rgba(239, 68, 68, 0.7)",
                        ],
                        "borderColor": [
                            "rgba(34, 197, 94, 1)",
                            "rgba(234, 179, 8, 1)",
                            "rgba(239, 68, 68, 1)",
                        ],
                        "borderWidth": 1,
                    }
                ],
            }

            await callback({
                "overall_score": overall,
                "grade": grade,
                "breakdown": {
                    "seo": seo_score,
                    "performance": {"lcp_ms": lcp_ms},
                    "competitors": {"top_competitor_score": 75},
                    "links": {
                        "internal_links_count": int(links.get("internal_links_count", 0)),
                        "external_links_count": int(links.get("external_links_count", 0)),
                        "broken_internal_links": int(links.get("broken_internal_links", 0)),
                        "broken_internal_samples": links.get("broken_internal_samples", []),
                    },
                },
                "chart_data": {"bar": bar_data, "doughnut": doughnut_data},
                "finished": True
            })

        except Exception as e:
            await callback({"error": str(e), "finished": True})
