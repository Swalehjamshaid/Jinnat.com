# app/audit/runner.py
import os
import time
import json
import inspect
import asyncio
from typing import Any, Dict, Callable, Awaitable, Optional, List, Tuple
import httpx
from bs4 import BeautifulSoup

# Import analyzer modules — add new ones here when you create them
from app.audit import seo as seo_mod
from app.audit import links as links_mod
from app.audit import performance as perf_mod
from app.audit import competitor_report as comp_mod
# Future analyzers go here — just import and add to ANALYZER_REGISTRY
# from app.audit import accessibility as access_mod
# from app.audit import mobile as mobile_mod
# from app.audit import security as sec_mod
# from app.audit import content_quality as content_mod

from app.audit.grader import compute_grade
from app.audit.record import save_audit_record

# ============================================================
# Core Helpers — very tolerant
# ============================================================

def _env_flag(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    return default if val is None else str(val).strip().lower() in ("1", "true", "yes", "on")


AUDIT_DEBUG = _env_flag("AUDIT_DEBUG", False)


def _log_debug(diag: List[str], msg: str):
    if AUDIT_DEBUG:
        diag.append(msg)


def _select_kwargs(func: Callable, pool: Dict[str, Any]) -> Dict[str, Any]:
    try:
        sig = inspect.signature(func)
        return {k: v for k, v in pool.items() if k in sig.parameters}
    except Exception:
        return {}


async def _maybe_call(func: Optional[Callable], diag: List[str], **pool) -> Any:
    if not callable(func):
        return None

    kwargs = _select_kwargs(func, pool)
    try:
        res = func(**kwargs)
        if asyncio.iscoroutine(res):
            res = await res
        return res
    except TypeError:
        try:
            res = func()
            if asyncio.iscoroutine(res):
                res = await res
            return res
        except Exception as e:
            _log_debug(diag, f"Call failed: {e}")
            return None
    except Exception as e:
        _log_debug(diag, f"Analyzer error: {e}")
        return None


def _extract_score(raw: Any, default: int = 0) -> int:
    if raw is None:
        return default
    if isinstance(raw, (int, float)):
        return int(round(float(raw)))
    if isinstance(raw, dict):
        for k in ("score", "value", "total", "overall", "points", "percent", "rating", "result"):
            if k in raw:
                try:
                    return int(round(float(raw[k])))
                except:
                    pass
        for parent in ("metrics", "data", "result", "summary", "scores", "details", "analysis"):
            if parent in raw and isinstance(raw[parent], dict):
                v = _extract_score(raw[parent], None)
                if v is not None:
                    return v
        for v in raw.values():
            score = _extract_score(v, None)
            if score is not None:
                return score
    if isinstance(raw, (list, tuple)):
        for item in raw:
            v = _extract_score(item, None)
            if v is not None:
                return v
    return default


def _normalize_links(links_raw: Any) -> Dict[str, int]:
    """
    IMPORTANT: Output shape MUST NOT CHANGE — preserves exact compatibility with HTML
    """
    base = {
        "internal_links_count": 0,
        "external_links_count": 0,
        "warning_links_count": 0,
        "broken_internal_links": 0,
    }

    if not links_raw:
        return base

    def _update(d: dict):
        for k, v in d.items():
            norm_k = str(k).lower()
            if "internal" in norm_k and isinstance(v, (int, float)):
                base["internal_links_count"] = int(v)
            elif "external" in norm_k and isinstance(v, (int, float)):
                base["external_links_count"] = int(v)
            elif any(w in norm_k for w in ("warn", "caution", "suspicious", "risk")):
                base["warning_links_count"] = int(v) if isinstance(v, (int, float)) else base["warning_links_count"]
            elif any(w in norm_k for w in ("broken", "error", "404", "fail", "dead")):
                base["broken_internal_links"] = int(v) if isinstance(v, (int, float)) else base["broken_internal_links"]

    if isinstance(links_raw, dict):
        _update(links_raw)
        base.update({k: int(v) for k, v in links_raw.items() if k in base})
    elif isinstance(links_raw, (list, tuple)):
        for item in links_raw:
            if isinstance(item, dict):
                _update(item)

    return base


# ============================================================
# Analyzer Registry — single place to add new modules
# ============================================================

ANALYZER_REGISTRY = [
    ("seo", seo_mod),
    ("performance", perf_mod),
    ("links", links_mod),
    ("competitors", comp_mod),
    # Add any new analyzer here — only one line needed
    # ("accessibility", access_mod),
    # ("mobile_friendly", mobile_mod),
    # ("security_headers", sec_mod),
    # ("content_quality", content_mod),
]


def discover_analyzer_functions(module) -> List[Tuple[str, Callable]]:
    """
    Discover all functions/coroutines that look like analyzers.
    Very tolerant — runs almost everything that is callable.
    """
    candidates = []
    for name, obj in inspect.getmembers(module, lambda o: inspect.isfunction(o) or inspect.iscoroutinefunction(o)):
        lower = name.lower()
        # Prefer functions that sound like analyzers
        if any(kw in lower for kw in (
            "calculate", "analyze", "get", "score", "check", "report", "audit",
            "evaluate", "measure", "extract", "detect", "compute"
        )):
            candidates.append((name, obj))
        # Fallback: most callables are useful except helpers/tests
        elif not any(ex in lower for ex in ("test", "helper", "util", "internal", "private", "main")):
            candidates.append((name, obj))

    # Sort: analyzer-like names first
    candidates.sort(key=lambda x: (
        0 if any(w in x[0].lower() for w in ("calculate", "analyze", "score", "audit")) else 1,
        x[0]
    ))

    return candidates[:10]  # safety limit


# ============================================================
# Main Runner — maximum flexibility
# ============================================================

class WebsiteAuditRunner:
    def __init__(self, url: str):
        self.url = url if url.startswith(("http://", "https://")) else f"https://{url}"

    async def run_audit(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]):
        diag: List[str] = []
        breakdown: Dict[str, Any] = {}
        all_charts: List[Dict] = []
        top_scores: Dict[str, int] = {}

        try:
            await callback({"status": "🚀 Starting audit...", "crawl_progress": 5})

            # Fetch page once — shared context for all analyzers
            start = time.time()
            await callback({"status": "🌐 Fetching HTML...", "crawl_progress": 15})

            async with httpx.AsyncClient(timeout=30, verify=False) as client:
                resp = await client.get(self.url, follow_redirects=True, headers={"User-Agent": "FF-Audit/1.0"})
                resp.raise_for_status()
                html = resp.text

            soup = BeautifulSoup(html, "html.parser")
            fetch_ms = int((time.time() - start) * 1000)

            context = {
                "url": self.url,
                "html": html,
                "soup": soup,
                "fetch_ms": fetch_ms,
                "callback": callback,  # allow analyzers to report sub-progress
            }

            # Execute all analyzer categories
            progress = 20
            step = 65 / max(1, len(ANALYZER_REGISTRY))

            for category, module in ANALYZER_REGISTRY:
                progress += int(step)
                await callback({"status": f"🔍 {category.title()} analysis...", "crawl_progress": progress})

                functions = discover_analyzer_functions(module)
                category_result = {}

                for fname, func in functions:
                    raw = await _maybe_call(func, diag, **context)
                    if raw is not None:
                        category_result[fname] = raw

                        score = _extract_score(raw)
                        if score > 0:
                            category_result[f"{fname}_score"] = score
                            top_scores[category] = score

                        # Collect charts from any analyzer
                        if isinstance(raw, dict):
                            if "chart" in raw and isinstance(raw["chart"], dict):
                                chart = raw["chart"]
                                chart.setdefault("title", f"{category} - {fname}")
                                all_charts.append(chart)
                            if "charts" in raw and isinstance(raw["charts"], (list, tuple)):
                                for ch in raw["charts"]:
                                    if isinstance(ch, dict):
                                        ch.setdefault("title", f"{category} chart")
                                        all_charts.append(ch)

                if category_result:
                    breakdown[category] = category_result

            # Links — preserve exact shape
            links_raw = breakdown.get("links", {})
            links_normalized = _normalize_links(links_raw)

            # Competitors — use enhanced details if available
            comp_raw = breakdown.get("competitors", {})
            comp_names = _coerce_names(comp_raw)
            comp_score = _extract_score(comp_raw, 0)

            # Try to get clean 3 names from competitor_report enhanced output
            if comp_mod and hasattr(comp_mod, "get_last_competitor_details"):
                details = comp_mod.get_last_competitor_details()
                if details and "competitors" in details:
                    comp_names = details["competitors"].get("names", comp_names)
                    comp_score = details["target"].get("score", comp_score)

            # Final grade
            seo_score = top_scores.get("seo", 0)
            perf_score = top_scores.get("performance", 0)
            overall, grade = compute_grade(seo_score, perf_score, comp_score)

            # Fallback charts for old HTML compatibility
            fallback_charts = {
                "bar": {
                    "labels": ["SEO", "Speed", "Competitors"],
                    "datasets": [{
                        "label": "Scores",
                        "data": [seo_score, perf_score, comp_score],
                        "backgroundColor": ["#FFD700", "#3B82F6", "#10B981"],
                        "borderColor": ["#FFD700", "#3B82F6", "#10B981"],
                        "borderWidth": 1
                    }]
                },
                "doughnut": {
                    "labels": ["Internal", "Warnings", "Broken"],
                    "datasets": [{
                        "data": [
                            links_normalized["internal_links_count"],
                            links_normalized["warning_links_count"],
                            links_normalized["broken_internal_links"]
                        ],
                        "backgroundColor": ["#22C55E", "#EAB308", "#EF4444"],
                        "borderColor": ["#22C55E", "#EAB308", "#EF4444"],
                        "borderWidth": 1
                    }]
                }
            }

            # Final payload — extremely flexible shape
            payload = {
                "overall_score": overall,
                "grade": grade,
                "scores": top_scores,                     # quick access to category scores
                "breakdown": breakdown,                   # full raw results from every analyzer
                "links": links_normalized,                # ← EXACT shape preserved
                "competitors": {
                    "names": comp_names[:3],              # top 3 names
                    "top_competitor_score": comp_score,
                    "raw": comp_raw
                },
                "chart_data": fallback_charts,            # old HTML compatibility
                "charts": all_charts,                     # flexible list — any analyzer can contribute
                "fetch_ms": fetch_ms,
                "finished": True,
                "audit_time": time.time(),
            }

            if AUDIT_DEBUG:
                payload["debug"] = {"trace": diag}

            await callback(payload)

            # Save record — kept compatible
            save_audit_record(self.url, {
                "seo": seo_score,
                "performance": perf_score,
                "competitor": comp_score,
                "links": links_normalized,
                "overall": overall,
                "grade": grade,
                "fetch_ms": fetch_ms,
                "competitor_names": comp_names[:3]
            })

        except Exception as e:
            error = {"error": f"Runner failed: {str(e)}", "finished": True}
            if AUDIT_DEBUG:
                error["debug"] = {"trace": diag}
            await callback(error)
