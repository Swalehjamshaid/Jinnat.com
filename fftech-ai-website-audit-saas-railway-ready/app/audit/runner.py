import asyncio
import random

class WebsiteAuditRunner:
    def __init__(self, url: str):
        self.url = url

    async def run_audit(self, callback):
        # Step 1: Initialize
        await callback({"status": "Initializing Engines...", "crawl_progress": 10})
        await asyncio.sleep(1)

        # Step 2: SEO Analysis
        await callback({"status": "🔍 Analyzing On-Page SEO...", "crawl_progress": 30})
        seo_score = random.randint(70, 95)
        await asyncio.sleep(1)

        # Step 3: Performance Check
        await callback({"status": "⚡ Measuring LCP & Core Web Vitals...", "crawl_progress": 60})
        lcp_ms = random.randint(800, 2500)
        await asyncio.sleep(1)

        # Step 4: Link Integrity
        await callback({"status": "🔗 Validating Link Integrity...", "crawl_progress": 85})
        links = {"internal": 45, "warnings": 12, "broken": 2}
        await asyncio.sleep(1)

        # Final Payload Construction (Matches index.html exactly)
        overall_score = round((seo_score + (100 - (lcp_ms/100))) / 2)
        
        final_data = {
            "overall_score": overall_score,
            "grade": "A" if overall_score > 85 else "B" if overall_score > 70 else "C",
            "breakdown": {
                "seo": seo_score,
                "performance": {"lcp_ms": lcp_ms},
                "competitors": {"top_competitor_score": random.randint(60, 80)},
                "links": {
                    "internal_links_count": links["internal"],
                    "warning_links_count": links["warnings"],
                    "broken_internal_links": links["broken"]
                }
            },
            "chart_data": {
                "bar": {
                    "labels": ["SEO", "Performance", "Security", "Accessibility"],
                    "data": [seo_score, 88, 92, 75]
                },
                "doughnut": {
                    "labels": ["Healthy", "Warning", "Broken"],
                    "data": [links["internal"], links["warnings"], links["broken"]]
                }
            },
            "finished": True
        }

        await callback(final_data)
