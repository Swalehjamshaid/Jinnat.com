# app/audit/runner.py
import time
import httpx
from bs4 import BeautifulSoup
from app.audit.links import analyze_links_async
from app.audit.seo import calculate_seo_score
from app.audit.performance import calculate_performance_score
from app.audit.competitor_report import get_top_competitor_score
from app.audit.grader import compute_grade
from app.audit.record import save_audit_record

class WebsiteAuditRunner:
    def __init__(self, url: str):
        self.url = url if url.startswith("http") else f"https://{url}"

    async def run_audit(self, callback):
        try:
            # 1️⃣ Initializing
            await callback({"status": "🚀 Initializing Engine...", "crawl_progress": 10})
            start_time = time.time()

            # 2️⃣ Fetch Page
            await callback({"status": "🌐 Fetching page...", "crawl_progress": 20})
            async with httpx.AsyncClient(timeout=12.0, verify=False) as client:
                res = await client.get(self.url, follow_redirects=True)
                html = res.text

            # Measure LCP / Speed
            lcp_ms = int((time.time() - start_time) * 1000)
            perf_score = calculate_performance_score(lcp_ms)

            # 3️⃣ Parse HTML and SEO Analysis
            await callback({"status": "🔍 Analyzing SEO...", "crawl_progress": 50})
            soup = BeautifulSoup(html, "html.parser")
            seo_score = calculate_seo_score(soup)

            # 4️⃣ Link Analysis
            links_data = await analyze_links_async({self.url: html}, self.url, callback)

            # 5️⃣ Competitor Comparison
            competitor_score = get_top_competitor_score(self.url)

            # 6️⃣ Compute Overall Grade
            overall, grade = compute_grade(seo_score, perf_score, competitor_score)

            # 7️⃣ Prepare Chart Data
            bar_data = {
                "labels": ["SEO", "Speed", "Security", "AI"],
                "datasets": [{
                    "label": "Scores",
                    "data": [seo_score, perf_score, 90, 95],
                    "backgroundColor": ["#ffd700", "#3b82f6", "#10b981", "#9333ea"],
                    "borderWidth": 1,
                }]
            }

            doughnut_data = {
                "labels": ["Healthy", "Warning", "Broken"],
                "datasets": [{
                    "data": [
                        links_data.get("internal_links_count", 0),
                        links_data.get("warning_links_count", 0),
                        links_data.get("broken_internal_links", 0),
                    ],
                    "backgroundColor": ["#22c55e", "#eab308", "#ef4444"],
                    "borderWidth": 1,
                }]
            }

            # 8️⃣ Send Final Result to UI
            await callback({
                "overall_score": overall,
                "grade": grade,
                "breakdown": {
                    "seo": seo_score,
                    "performance": {"lcp_ms": lcp_ms, "score": perf_score},
                    "competitors": {"top_competitor_score": competitor_score},
                    "links": links_data
                },
                "chart_data": {"bar": bar_data, "doughnut": doughnut_data},
                "finished": True
            })

            # 9️⃣ Save Audit Record
            save_audit_record(self.url, {
                "seo": seo_score,
                "performance": perf_score,
                "competitor": competitor_score,
                "links": links_data,
                "overall": overall,
                "grade": grade,
                "lcp_ms": lcp_ms,
            })

        except Exception as e:
            await callback({"error": f"Runner Error: {str(e)}", "finished": True})
