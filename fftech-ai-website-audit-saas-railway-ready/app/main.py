import time
import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any, Callable, Awaitable, List, Tuple

# All analysis modules — add new imports & entries here only
from app.audit.links import analyze_links_async
from app.audit.seo import calculate_seo_score
from app.audit.performance import calculate_performance_score
from app.audit.competitor_report import get_top_competitor_score
from app.audit.grader import compute_grade
from app.audit.record import save_audit_record


class WebsiteAuditRunner:
    def __init__(self, url: str):
        self.url = url if url.startswith("http") else f"https://{url}"

    async def run_audit(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]):
        """
        Flexible audit orchestrator:
        - Runs all registered analysis modules automatically
        - Builds dynamic breakdown, charts, and progress
        - New modules appear in output without changing this file
        - Graceful error handling & defaults
        """
        results: Dict[str, Any] = {}
        start_time = time.time()

        try:
            # ──── 1. Initialize ─────────────────────────────────────────────
            await callback({"status": "🚀 Initializing Audit Engine...", "crawl_progress": 5})

            # ──── 2. Fetch page ─────────────────────────────────────────────
            await callback({"status": "🌐 Fetching target page...", "crawl_progress": 20})
            async with httpx.AsyncClient(timeout=12.0, verify=False) as client:
                res = await client.get(self.url, follow_redirects=True)
                html = res.text

            lcp_ms = int((time.time() - start_time) * 1000)

            # ──── 3. Parse HTML once (shared soup) ──────────────────────────
            soup = BeautifulSoup(html, "lxml")  # faster parser (install lxml if possible)

            # ──── 4. Dynamic analysis pipeline ──────────────────────────────
            # Add new module here when created — auto-included everywhere
            analysis_steps: List[Tuple[str, Callable]] = [
                ("seo", lambda: calculate_seo_score(soup)),
                ("performance", lambda: calculate_performance_score(lcp_ms)),
                ("links", lambda: analyze_links_async({self.url: html}, self.url, callback)),
                ("competitor", lambda: get_top_competitor_score(self.url)),
                # Future modules — just add line:
                # ("security", lambda: calculate_security_score(soup, self.url)),
                # ("content", lambda: calculate_content_quality(soup)),
                # ("accessibility", lambda: calculate_accessibility_score(soup)),
            ]

            await callback({"status": f"Running {len(analysis_steps)} analysis modules...", "crawl_progress": 30})

            for idx, (module_name, func) in enumerate(analysis_steps, 1):
                try:
                    result = await func() if asyncio.iscoroutinefunction(func) else func()
                    results[module_name] = result or {}
                    progress = 30 + int(60 * (idx / len(analysis_steps)))
                    await callback({
                        "status": f"Completed {module_name.capitalize()} analysis",
                        "crawl_progress": progress
                    })
                except Exception as exc:
                    results[module_name] = {"error": str(exc)}
                    await callback({
                        "status": f"{module_name.capitalize()} failed: {str(exc)}",
                        "crawl_progress": 35 + int(50 * (idx / len(analysis_steps)))
                    })

            # ──── 5. Extract common values with safe defaults ───────────────
            seo_score = results.get("seo", {}).get("seo_score", 0)
            perf_score = results.get("performance", {}).get("score", 0)
            competitor_score = results.get("competitor", {}).get("top_competitor_score", 75)
            links_data = results.get("links", {})

            # Ensure required link keys exist
            for key in ["internal_links_count", "external_links_count", "warning_links_count", "broken_internal_links"]:
                links_data.setdefault(key, 0)

            # ──── 6. Compute final grade ────────────────────────────────────
            overall, grade = compute_grade(seo_score, perf_score, competitor_score)

            # ──── 7. Build dynamic charts ───────────────────────────────────
            # Bar chart — auto-includes all numeric scores from modules
            bar_labels = ["SEO", "Speed"]
            bar_values = [seo_score, perf_score]

            # Security & AI still placeholders — but dynamic if modules added
            bar_labels += ["Security", "AI"]
            bar_values += [90, 95]

            # Add any other numeric scores from modules
            for module_name, data in results.items():
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, (int, float)) and k not in ["lcp_ms", "score", "seo_score"]:
                            label = k.replace("_", " ").title()
                            bar_labels.append(label)
                            bar_values.append(int(v))

            bar_data = {
                "labels": bar_labels,
                "datasets": [{
                    "label": "Scores",
                    "data": bar_values,
                    "backgroundColor": [
                        "#ffd700", "#3b82f6", "#10b981", "#9333ea"
                    ] * (len(bar_labels) // 4 + 1),
                    "borderWidth": 1,
                }]
            }

            # Doughnut chart — flexible if more categories added later
            doughnut_data = {
                "labels": ["Healthy", "Warning", "Broken"],
                "datasets": [{
                    "data": [
                        int(links_data.get("internal_links_count", 0)),
                        int(links_data.get("warning_links_count", 0)),
                        int(links_data.get("broken_internal_links", 0)),
                    ],
                    "backgroundColor": ["#22c55e", "#eab308", "#ef4444"],
                    "borderWidth": 1,
                }]
            }

            # ──── 8. Final payload — fully dynamic & backward compatible ────
            final_payload = {
                "overall_score": overall,
                "grade": grade,
                "breakdown": {
                    "seo": seo_score,
                    "performance": {"lcp_ms": lcp_ms, "score": perf_score},
                    "competitors": {"top_competitor_score": competitor_score},
                    "links": links_data,
                    # Any new module results appear here automatically
                    **{k: v for k, v in results.items() if k not in ["seo", "performance", "links", "competitor"]}
                },
                "chart_data": {
                    "bar": bar_data,
                    "doughnut": doughnut_data
                },
                "finished": True
            }

            await callback(final_payload)

            # ──── 9. Save record — also dynamic ─────────────────────────────
            save_audit_record(self.url, {
                "seo": seo_score,
                "performance": perf_score,
                "competitor": competitor_score,
                "links": links_data,
                "overall": overall,
                "grade": grade,
                "lcp_ms": lcp_ms,
                # Automatically include everything
                **results
            })

        except Exception as e:
            await callback({
                "error": f"Audit failed: {str(e)}",
                "finished": True
            })
