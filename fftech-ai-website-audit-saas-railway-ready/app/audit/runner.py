# app/audit/runner.py
import time
import inspect
import asyncio
import httpx
from bs4 import BeautifulSoup

from app.audit import seo as seo_mod
from app.audit import links as links_mod
from app.audit import performance as perf_mod
from app.audit import competitor_report as comp_mod
from app.audit.grader import compute_grade
from app.audit.record import save_audit_record


# -------------------------------
# FLEX HELPERS (CORE MECHANISM)
# -------------------------------

def _is_async(fn):
    return asyncio.iscoroutinefunction(fn)

async def _call(fn, **pool):
    """
    Call ANY function (sync/async), with only the args it accepts.
    """
    if not callable(fn):
        return None

    try:
        sig = inspect.signature(fn)
        accepted = {k: v for k, v in pool.items() if k in sig.parameters}
    except Exception:
        accepted = {}

    try:
        result = fn(**accepted)
        return await result if asyncio.iscoroutine(result) else result
    except Exception:
        try:
            result = fn()
            return await result if asyncio.iscoroutine(result) else result
        except Exception:
            return None


def _extract_score(raw, default=0):
    """
    Extract int from ANY output shape.
    Accepted formats:
    - int
    - float
    - dict with keys: score/value/total
    - list/tuple of any above
    """
    if raw is None:
        return default

    if isinstance(raw, (int, float)):
        return int(raw)

    if isinstance(raw, dict):
        for key in ("score", "value", "total", "overall"):
            if key in raw:
                try:
                    return int(raw[key])
                except:
                    pass

    if isinstance(raw, (list, tuple)):
        for x in raw:
            s = _extract_score(x, None)
            if s is not None:
                return s

    return default


# -------------------------------
# MAIN CLASS
# -------------------------------

class WebsiteAuditRunner:
    def __init__(self, url: str):
        self.url = url if url.startswith("http") else f"https://{url}"

    async def run_audit(self, callback):
        try:
            await callback({"status": "🚀 Starting...", "crawl_progress": 5})

            start = time.time()

            # ---------------------------
            # 1) Fetch HTML (unchanged)
            # ---------------------------
            await callback({"status": "🌐 Fetching HTML...", "crawl_progress": 15})
            async with httpx.AsyncClient(timeout=15, verify=False) as client:
                res = await client.get(self.url, follow_redirects=True)
                html = res.text

            soup = BeautifulSoup(html, "html.parser")
            lcp_ms = int((time.time() - start) * 1000)

            # Shared input pool for ALL modules
            shared_args = {
                "url": self.url,
                "html": html,
                "soup": soup,
                "lcp_ms": lcp_ms,
            }

            # ---------------------------
            # 2) Performance (dynamic)
            # ---------------------------
            await callback({"status": "⚡ Performance...", "crawl_progress": 35})
            perf_fn = getattr(perf_mod, "calculate_performance_score", None)
            perf_result = await _call(perf_fn, **shared_args)
            perf_score = _extract_score(perf_result)
            perf_extras = perf_result

            # ---------------------------
            # 3) SEO (dynamic)
            # ---------------------------
            await callback({"status": "🔍 SEO...", "crawl_progress": 50})
            seo_fn = getattr(seo_mod, "calculate_seo_score", None)
            seo_result = await _call(seo_fn, **shared_args)
            seo_score = _extract_score(seo_result)
            seo_extras = seo_result

            # ---------------------------
            # 4) Links (dynamic)
            # ---------------------------
            await callback({"status": "🔗 Analyzing Links...", "crawl_progress": 65})
            links_fn = getattr(links_mod, "analyze_links_async", None)
            links_result = await _call(links_fn, pages={self.url: html}, base_url=self.url, callback=callback, **shared_args) or {}

            # Safety defaults
            links_result.setdefault("internal_links_count", 0)
            links_result.setdefault("external_links_count", 0)
            links_result.setdefault("warning_links_count", 0)
            links_result.setdefault("broken_internal_links", 0)

            # ---------------------------
            # 5) Competitors (dynamic)
            # ---------------------------
            await callback({"status": "📊 Competitors...", "crawl_progress": 75})

            # optional competitor list
            comp_items = None
            comp_names = None

            if hasattr(comp_mod, "get_competitors_with_scores"):
                comp_items = await _call(comp_mod.get_competitors_with_scores, **shared_args)

            if hasattr(comp_mod, "get_competitors"):
                comp_names = await _call(comp_mod.get_competitors, **shared_args)

            # always provide primary legacy score
            comp_score_fn = getattr(comp_mod, "get_top_competitor_score", None)
            comp_score = await _call(comp_score_fn, **shared_args)

            # ---------------------------
            # 6) Grade
            # ---------------------------
            overall, grade = compute_grade(seo_score, perf_score, comp_score)

            # ---------------------------
            # 7) Chart Data (unchanged)
            # ---------------------------
            bar = {
                "labels": ["SEO", "Speed", "Security", "AI"],
                "datasets": [{
                    "label": "Scores",
                    "data": [seo_score, perf_score, 90, 95]
                }]
            }

            doughnut = {
                "labels": ["Healthy", "Warning", "Broken"],
                "datasets": [{
                    "data": [
                        links_result["internal_links_count"],
                        links_result["warning_links_count"],
                        links_result["broken_internal_links"],
                    ]
                }]
            }

            # ---------------------------
            # 8) Final Output (EXTREMELY FLEXIBLE)
            # ---------------------------
            await callback({
                "overall_score": overall,
                "grade": grade,
                "breakdown": {
                    "seo": seo_score,
                    "seo_extras": seo_extras,
                    "performance": {"lcp_ms": lcp_ms, "score": perf_score, "extras": perf_extras},
                    "competitors": {
                        "top_competitor_score": comp_score,
                        "names": comp_names,
                        "items": comp_items,
                    },
                    "links": links_result,
                },
                "chart_data": {"bar": bar, "doughnut": doughnut},
                "finished": True,
            })

            # ---------------------------
            # 9) Save record
            # ---------------------------
            save_audit_record(self.url, {
                "seo": seo_score,
                "performance": perf_score,
                "competitor": comp_score,
                "links": links_result,
                "overall": overall,
                "grade": grade,
                "lcp_ms": lcp_ms,
                "competitor_names": comp_names,
            })

        except Exception as e:
            await callback({"error": f"Runner Error: {e}", "finished": True})
