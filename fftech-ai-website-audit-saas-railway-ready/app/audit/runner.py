import asyncio
import httpx
from bs4 import BeautifulSoup
import time
import traceback
from app.audit.link import analyze_links_async

class WebsiteAuditRunner:
    def __init__(self, url: str):
        self.url = url.strip()
        if not self.url.startswith(('http://', 'https://')):
            self.url = f"https://{self.url}"

    async def run_audit(self, callback):
        try:
            await callback({"status": "🚀 Initializing Real-Time Engine...", "crawl_progress": 10})
            start_time = time.time()
            
            # --- PHASE 1: HTTP REQUEST ---
            # Global 10s timeout to prevent the entire engine from hanging
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, verify=False) as client:
                await callback({"status": "⚡ Connecting to Server...", "crawl_progress": 25})
                response = await client.get(self.url)
                lcp_ms = int((time.time() - start_time) * 1000)
                html_content = response.text
                
            # --- PHASE 2: SEO SCRAPE ---
            await callback({"status": "🔍 Scraping Metadata...", "crawl_progress": 50})
            soup = BeautifulSoup(html_content, 'lxml')
            
            title = soup.title.string if soup.title else None
            h1_count = len(soup.find_all('h1'))
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            
            seo_points = 0
            if title: seo_points += 40
            if meta_desc: seo_points += 30
            if h1_count > 0: seo_points += 30
            
            # --- PHASE 3: LINK ANALYSIS ---
            # This calls the optimized link.py
            link_data = await analyze_links_async(
                html_input={self.url: html_content}, 
                base_url=self.url,
                progress_callback=callback
            )

            # --- PHASE 4: SCORING ---
            speed_score = max(0, 100 - (lcp_ms // 50)) 
            overall_score = int((seo_points * 0.6) + (speed_score * 0.4))
            
            final_payload = {
                "overall_score": overall_score,
                "grade": "A" if overall_score > 85 else "B" if overall_score > 70 else "D",
                "breakdown": {
                    "seo": seo_points,
                    "performance": {"lcp_ms": lcp_ms},
                    "competitors": {"top_competitor_score": 72},
                    "links": link_data
                },
                "chart_data": {
                    "bar": {
                        "labels": ["SEO", "Speed", "Links", "AI Trust"],
                        "data": [seo_points, speed_score, 85, 90]
                    },
                    "doughnut": {
                        "labels": ["Healthy", "Warning", "Broken"],
                        "data": [
                            link_data["internal_links_count"], 
                            link_data["warning_links_count"], 
                            link_data["broken_internal_links"]
                        ]
                    }
                },
                "finished": True
            }
            await callback(final_payload)

        except httpx.TimeoutException:
            await callback({"error": "Target site is too slow (Timeout).", "finished": True})
        except Exception as e:
            await callback({"error": f"Audit Error: {str(e)}", "finished": True})
            print(f"TRACEBACK: {traceback.format_exc()}")
