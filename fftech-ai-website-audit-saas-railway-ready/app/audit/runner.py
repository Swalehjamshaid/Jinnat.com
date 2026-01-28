# app/audit/runner.py
import os
import time
import json
import inspect
import asyncio
from typing import Any, Dict, Callable, Awaitable, Optional, List, Tuple
import httpx
from bs4 import BeautifulSoup

# Import analyzer modules — add new ones here when created
from app.audit import seo as seo_mod
from app.audit import links as links_mod
from app.audit import performance as perf_mod
from app.audit import competitor_report as comp_mod
# Example future imports (uncomment when you add them):
# from app.audit import accessibility as access_mod
# from app.audit import mobile as mobile_mod
# from app.audit import security as sec_mod

from app.audit.grader import compute_grade
from app.audit.record import save_audit_record

# ============================================================
# Core Flex Helpers (mostly unchanged)
# ============================================================

def _env_flag(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


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
            _log_debug(diag, f"Analyzer call failed: {e}")
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
        for k in ("score", "value", "total", "overall", "points", "percent", "rating"):
            if k in raw:
                try:
                    return int(round(float(raw[k])))
                except:
                    pass
        for parent in ("metrics", "data", "result", "summary", "scores", "details"):
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


def _coerce_names(value: Any, limit: int = 6) -> List[str]:
    out: List[str] = []

    def _add(name):
        if isinstance(name, str):
            n = name.strip()
            if n and n not in out:
                out.append(n)

    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, str):
                _add(item)
            elif isinstance(item, dict):
                for k in ("name", "brand", "title", "label", "domain", "site", "company", "url"):
                    if k in item and isinstance(item[k], str):
                        _add(item[k])
                        break
    elif isinstance(value, dict):
        if "names" in value:
            out.extend(_coerce_names(value["names"], limit))
        for k in ("name", "brand", "title", "label", "domain"):
            if k in value and isinstance(value[k], str):
                _add(value[k])
    elif isinstance(value, str):
        _add(value)

    return out[:limit]


def _normalize_links(links_raw: Any) -> Dict[str, int]:
    """
    IMPORTANT: This function signature and output shape MUST NOT CHANGE
    to preserve compatibility with existing HTML frontend code.
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
            norm_k = k.lower()
            if "internal" in norm_k and isinstance(v, (int, float)):
                base["internal_links_count"] = int(v)
            elif "external" in norm_k and isinstance(v, (int, float)):
                base["external_links_count"] = int(v)
            elif any(w in norm_k for w in ("warn", "caution", "suspicious")):
                base["warning_links_count"] = int(v) if isinstance(v, (int, float)) else base["warning_links_count"]
            elif any(w in norm_k for w in ("broken", "error", "404", "fail")):
                base["broken_internal_links"] = int(v) if isinstance(v, (int, float)) else base["broken_internal_links"]

    if isinstance(links_raw, dict):
        _update(links_raw)
        base.update({k: int(v) for k, v in links_raw.items() if k in base and isinstance(v, (int, float))})
    elif isinstance(links_raw, (list, tuple)):
        for item in links_raw:
            if isinstance(item, dict):
                _update(item)

    return base


# ============================================================
# Analyzer Registry – add new categories here
# ============================================================

ANALYZER_REGISTRY = [
    ("seo", seo_mod),
    ("performance", perf_mod),
    ("links", links_mod),
    ("competitors", comp_mod),
    # Add new analyzer modules here when you create them:
    # ("accessibility", access_mod),
    # ("mobile", mobile_mod),
    # ("security", sec_mod),
    # ("content", content_mod),
]


def discover_analyzer_functions(module) -> List[Tuple[str, Callable]]:
    """
    Find likely analyzer functions in a module.
    Prioritizes names containing: calculate, analyze, get, score, check, report, audit
    """
    funcs = []
    for name, obj in inspect.getmembers(module, lambda o: inspect.isfunction(o) or inspect.iscoroutinefunction(o)):
        lower = name.lower()
        if any(keyword in lower for keyword in (
            "calculate", "analyze", "get", "score", "check", "report", "audit", "evaluate", "measure"
        )):
            funcs.append((name, obj))
        elif "main" not in lower and "test" not in lower and "helper" not in lower:
            funcs.append((name, obj))  # fallback

    # Sort: prefer more descriptive names first
    funcs.sort(key=lambda x: (
        0 if any(w in x[0].lower() for w in ("calculate", "analyze", "score")) else 1,
        x[0]
    ))

    return funcs[:8]  # reasonable limit


# ============================================================
# Main Runner – now extremely flexible
# ============================================================

class WebsiteAuditRunner:
    def __init__(self, url: str):
        self.url = url if url.startswith("http") else f"https://{url}"

    async def run_audit(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]):
        diag: List[str] = []
        breakdown: Dict[str, Any] = {}
        collected_charts: List[Dict] = []
        extracted_scores: Dict[str, int] = {}

        try:
            await callback({"status": "🚀 Audit engine starting...", "crawl_progress": 3})

            # Fetch page once
            start_time = time.time()
            await callback({"status": "🌐 Fetching webpage...", "crawl_progress": 12})
            async with httpx.AsyncClient(timeout=25, verify=False) as client:
                response = await client.get(self.url, follow_redirects=True)
                response.raise_for_status()
                html_content = response.text

            soup = BeautifulSoup(html_content, "html.parser")
            fetch_duration_ms = int((time.time() - start_time) * 1000)

            common_context = {
                "url": self.url,
                "html": html_content,
                "soup": soup,
                "fetch_time_ms": fetch_duration_ms,
                "callback": callback,           # some analyzers might want to report progress
            }

            # Run all registered analyzer categories
            progress_base = 20
            progress_step = 60 / max(1, len(ANALYZER_REGISTRY))

            for idx, (category_name, module) in enumerate(ANALYZER_REGISTRY):
                await callback({
                    "status": f"Analyzing {category_name.title()}...",
                    "crawl_progress": progress_base + int(idx * progress_step)
                })

                analyzers = discover_analyzer_functions(module)
                category_data = {}

                for func_name, func in analyzers:
                    result = await _maybe_call(func, diag, **common_context)
                    if result is not None:
                        category_data[func_name] = result

                        # Try to extract a numeric score
                        score = _extract_score(result)
                        if score != 0:
                            category_data[f"{func_name}_score"] = score
                            extracted_scores[category_name] = score

                        # Collect charts if analyzer returned any
                        if isinstance(result, dict):
                            if "chart" in result:
                                chart = result["chart"]
                                if isinstance(chart, dict):
                                    chart.setdefault("title", f"{category_name} - {func_name}")
                                    collected_charts.append(chart)
                            elif "charts" in result and isinstance(result["charts"], list):
                                for ch in result["charts"]:
                                    if isinstance(ch, dict):
                                        ch.setdefault("title", f"{category_name} chart")
                                        collected_charts.append(ch)

                if category_data:
                    breakdown[category_name] = category_data

            # Special handling for links (keep exact output shape)
            links_result = breakdown.get("links", {})
            normalized_links = _normalize_links(links_result)

            # Competitors special handling (keep names & score)
            comp_data = breakdown.get("competitors", {})
            competitor_names = _coerce_names(comp_data)
            competitor_score = _extract_score(comp_data, 0)

            # Calculate final grade
            seo_s = extracted_scores.get("seo", 0)
            perf_s = extracted_scores.get("performance", 0)
            overall_score, final_grade = compute_grade(seo_s, perf_s, competitor_score)

            # Default charts for compatibility with old HTML
            fallback_charts = {
                "bar": {
                    "labels": ["SEO", "Performance", "Competitors"],
                    "datasets": [{
                        "label": "Scores",
                        "data": [seo_s, perf_s, competitor_score],
                        "backgroundColor": ["#FFD700aa", "#3B82F6aa", "#10B981aa"],
                        "borderColor": ["#FFD700", "#3B82F6", "#10B981"],
                        "borderWidth": 1
                    }]
                },
                "doughnut": {
                    "labels": ["Internal", "Warnings", "Broken"],
                    "datasets": [{
                        "data": [
                            normalized_links["internal_links_count"],
                            normalized_links["warning_links_count"],
                            normalized_links["broken_internal_links"]
                        ],
                        "backgroundColor": ["#22C55Eaa", "#EAB308aa", "#EF4444aa"],
                        "borderColor": ["#22C55E", "#EAB308", "#EF4444"],
                        "borderWidth": 1
                    }]
                }
            }

            # Final payload — flexible + backward compatible
            payload = {
                "overall_score": overall_score,
                "grade": final_grade,
                "scores": extracted_scores,               # top-level quick access
                "breakdown": breakdown,                   # ALL raw analyzer results
                "links": normalized_links,                # ← exact shape preserved
                "competitors": {
                    "names": competitor_names,
                    "top_competitor_score": competitor_score,
                    "raw_data": comp_data
                },
                "chart_data": fallback_charts,            # old HTML expects dict
                "charts": collected_charts,               # new flexible list format
                "fetch_time_ms": fetch_duration_ms,
                "finished": True,
                "audit_timestamp": time.time(),
            }

            if AUDIT_DEBUG:
                payload["debug_info"] = {"execution_trace": diag}

            await callback(payload)

            # Save record (kept compatible)
            save_audit_record(self.url, {
                "seo": seo_s,
                "performance": perf_s,
                "competitor": competitor_score,
                "links": normalized_links,
                "overall": overall_score,
                "grade": final_grade,
                "fetch_time_ms": fetch_duration_ms,
                "competitor_names": competitor_names
            })

        except Exception as exc:
            error_payload = {
                "error": f"Audit execution failed: {str(exc)}",
                "finished": True
            }
            if AUDIT_DEBUG:
                error_payload["debug_info"] = {"trace": diag}
            await callback(error_payload)
