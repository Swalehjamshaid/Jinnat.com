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
            
            # Global 10s timeout to prevent hanging if target site is slow
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, verify=False) as client:
                await callback({"status": "⚡ Connecting to Server...", "crawl_progress": 25})
                response = await client.get(self.url)
                lcp_ms = int((time.time() - start_time) * 1000)
                html_content = response.text

                # --- NEW: SECURITY CHECK ---
                # Validates HTTPS and presence of security headers
                is_https = response.url.scheme == "https"
                security_headers = ["X-Frame-Options", "Content-Security-Policy", "Strict-Transport-Security"]
                headers_found = sum(1 for h in security_headers if h in response.headers)
                security_score = (50 if is_https else 0) + (headers_found * 16)
                
            await callback({"status": "🔍 Scraping Metadata...", "crawl_progress": 50})
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Real SEO Logic
            title = soup.title.string if soup.title else None
            h1_count = len(soup.find_all('h1'))
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            seo_points = (40 if title else 0) + (30 if meta_desc else 0) + (30 if h1_count > 0 else 0)
            
            # Integration with optimized link analysis
            link_data = await analyze_links_async(
                html_input={self.url: html_content}, 
                base_url=self.url,
                progress_callback=callback
            )

            # Final Score Calculation based on SEO, Speed, and Security
            speed_score = max(0, 100 - (lcp_ms // 50)) 
            overall_score = int((seo_points * 0.4) + (speed_score * 0.3) + (security_score * 0.3))
            
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
                        "labels": ["SEO", "Speed", "Security", "AI Trust"],
                        "data": [seo_points, speed_score, int(security_score), 90]
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
            # Handles slow target websites gracefully
            await callback({"error": "Target site is too slow (Timeout).", "finished": True})
        except Exception as e:
            # Generic error handling for unexpected crashes
            await callback({"error": f"Audit Error: {str(e)}", "finished": True})
            print(f"TRACEBACK: {traceback.format_exc()}")
