# app/audit/runner.py
import os
import time
import json
import inspect
import asyncio
from typing import Any, Dict, Callable, Awaitable, Optional, List

import httpx
from bs4 import BeautifulSoup

# Dependent analyzers (names stay consistent; signatures/returns may vary)
from app.audit import seo as seo_mod
from app.audit import links as links_mod
from app.audit import performance as perf_mod
from app.audit import competitor_report as comp_mod
from app.audit.grader import compute_grade
from app.audit.record import save_audit_record


# ============================================================
# Core Flex Helpers
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
    """Select only parameters the target function actually accepts."""
    try:
        sig = inspect.signature(func)
        return {k: v for k, v in pool.items() if k in sig.parameters}
    except Exception:
        return {}

async def _maybe_call(func: Optional[Callable], diag: List[str], **pool) -> Any:
    """
    Call ANY function (sync/async) with only accepted kwargs.
    If it fails, retry with no kwargs. Returns None on failure.
    """
    if not callable(func):
        _log_debug(diag, f"Skipped call: target not callable ({func})")
        return None

    kwargs = _select_kwargs(func, pool)
    try:
        res = func(**kwargs)
        if asyncio.iscoroutine(res):
            res = await res
        return res
    except TypeError as te:
        # Retry with no kwargs (some functions take zero args)
        _log_debug(diag, f"TypeError with kwargs {list(kwargs.keys())}: {te}; retrying with no args.")
        try:
            res = func()
            if asyncio.iscoroutine(res):
                res = await res
            return res
        except Exception as e:
            _log_debug(diag, f"Call failed with no args: {e}")
            return None
    except Exception as e:
        _log_debug(diag, f"Call error: {e}")
        return None

def _extract_score(raw: Any, default: int = 0, diag: Optional[List[str]] = None) -> int:
    """
    Extract an integer-like score from varied return shapes:
    - int / float
    - dict → 'score'|'value'|'total'|'overall' (or nested under 'metrics'/'data')
    - list/tuple → first item that yields a score
    """
    if raw is None:
        return default

    if isinstance(raw, (int, float)):
        return int(round(float(raw)))

    if isinstance(raw, dict):
        # flat known keys
        for k in ("score", "value", "total", "overall"):
            if k in raw:
                try:
                    return int(round(float(raw[k])))
                except Exception:
                    pass
        # nested common shapes
        for parent in ("metrics", "data", "result", "summary"):
            if parent in raw and isinstance(raw[parent], dict):
                v = _extract_score(raw[parent], None, diag)
                if v is not None:
                    return v
        # look inside lists in dict values
        for v in raw.values():
            vscore = _extract_score(v, None, diag)
            if vscore is not None:
                return vscore
        return default

    if isinstance(raw, (list, tuple)):
        for item in raw:
            v = _extract_score(item, None, diag)
            if v is not None:
                return v
        return default

    return default

def _coerce_names(value: Any, limit: int = 3) -> List[str]:
    """
    Coerce a variety of shapes into a list of competitor names:
    - ["LG", "Samsung", "TCL"]
    - [{"name": "LG"}, {"brand":"Samsung"}, {"title":"TCL"}, {"domain":"tcl.com"}]
    - tuple/list/mixed primitives
    """
    out: List[str] = []
    if value is None:
        return out

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
                for k in ("name", "brand", "title", "label", "domain"):
                    if k in item and isinstance(item[k], str):
                        _add(item[k])
                        break
    elif isinstance(value, dict):
        # if dict has a 'names' list
        if "names" in value and isinstance(value["names"], (list, tuple)):
            out.extend(_coerce_names(value["names"], limit))
        # single name-holding dict
        for k in ("name", "brand", "title", "label", "domain"):
            if k in value and isinstance(value[k], str):
                _add(value[k])
                break
    elif isinstance(value, str):
        _add(value)

    return out[:limit]

def _normalize_links(links_raw: Any) -> Dict[str, int]:
    """
    Normalize links output into the keys the HTML expects.
    """
    base = {
        "internal_links_count": 0,
        "external_links_count": 0,
        "warning_links_count": 0,
        "broken_internal_links": 0,
    }
    if not links_raw:
        return base

    if isinstance(links_raw, dict):
        base.update({k: int(v) for k, v in links_raw.items()
                     if k in base and isinstance(v, (int, float))})
        # Also try to coerce from alternative keys
        alt_map = {
            "internal": "internal_links_count",
            "external": "external_links_count",
            "warnings": "warning_links_count",
            "broken": "broken_internal_links",
        }
        for src, dest in alt_map.items():
            if src in links_raw and base[dest] == 0:
                try:
                    base[dest] = int(links_raw[src])
                except Exception:
                    pass
        return base

    if isinstance(links_raw, (list, tuple)):
        # look for dicts within list
        for item in links_raw:
            if isinstance(item, dict):
                d = _normalize_links(item)
                for k in base:
                    base[k] = base[k] or d.get(k, 0)
        return base

    return base


# ============================================================
# Main Runner
# ============================================================

class WebsiteAuditRunner:
    """
    Flexible runner that adapts to analyzer modules and guarantees
    the exact payload shape your HTML expects.
    """
    def __init__(self, url: str):
        self.url = url if url.startswith("http") else f"https://{url}"

    async def run_audit(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]):
        diag: List[str] = []
        try:
            await callback({"status": "🚀 Starting...", "crawl_progress": 5})

            start = time.time()

            # -------------------------------------------------
            # 1) Fetch HTML (single GET; downstream is offline)
            # -------------------------------------------------
            await callback({"status": "🌐 Fetching HTML...", "crawl_progress": 15})
            async with httpx.AsyncClient(timeout=15, verify=False) as client:
                res = await client.get(self.url, follow_redirects=True)
                res.raise_for_status()
                html = res.text
            soup = BeautifulSoup(html, "html.parser")
            lcp_ms = int((time.time() - start) * 1000)

            shared_args = {
                "url": self.url,
                "html": html,
                "soup": soup,
                "lcp_ms": lcp_ms,
            }

            # -------------------------------------------------
            # 2) Performance
            # -------------------------------------------------
            await callback({"status": "⚡ Performance...", "crawl_progress": 35})
            perf_fn = getattr(perf_mod, "calculate_performance_score", None)
            if not callable(perf_fn):
                # fallback: first callable containing 'perf' or 'speed'
                for name, fn in inspect.getmembers(perf_mod, callable):
                    if any(t in name.lower() for t in ("perf", "speed")):
                        perf_fn = fn
                        break
            perf_raw = await _maybe_call(perf_fn, diag, **shared_args)
            perf_score = _extract_score(perf_raw, default=0, diag=diag)
            perf_extras = perf_raw if isinstance(perf_raw, dict) else {"raw": perf_raw}

            # -------------------------------------------------
            # 3) SEO
            # -------------------------------------------------
            await callback({"status": "🔍 SEO...", "crawl_progress": 50})
            seo_fn = getattr(seo_mod, "calculate_seo_score", None)
            if not callable(seo_fn):
                for name, fn in inspect.getmembers(seo_mod, callable):
                    if "seo" in name.lower():
                        seo_fn = fn
                        break
            seo_raw = await _maybe_call(seo_fn, diag, **shared_args)
            seo_score = _extract_score(seo_raw, default=0, diag=diag)
            seo_extras = seo_raw if isinstance(seo_raw, dict) else {"raw": seo_raw}

            # -------------------------------------------------
            # 4) Links
            # -------------------------------------------------
            await callback({"status": "🔗 Analyzing Links...", "crawl_progress": 65})
            links_fn = getattr(links_mod, "analyze_links_async", None)
            if not callable(links_fn):
                for name, fn in inspect.getmembers(links_mod, callable):
                    if "link" in name.lower():
                        links_fn = fn
                        break
            links_raw = await _maybe_call(
                links_fn, diag,
                pages={self.url: html}, base_url=self.url, callback=callback, **shared_args
            )
            links_data = _normalize_links(links_raw)

            # -------------------------------------------------
            # 5) Competitors
            # -------------------------------------------------
            await callback({"status": "📊 Competitors...", "crawl_progress": 75})

            comp_items = None
            comp_names: List[str] = []

            if hasattr(comp_mod, "get_competitors_with_scores"):
                items_raw = await _maybe_call(comp_mod.get_competitors_with_scores, diag, **shared_args)
                # keep raw items if they're a list of dicts
                if isinstance(items_raw, list):
                    comp_items = items_raw
                    comp_names = _coerce_names(items_raw, limit=3)

            if not comp_names and hasattr(comp_mod, "get_competitors"):
                names_raw = await _maybe_call(comp_mod.get_competitors, diag, **shared_args)
                comp_names = _coerce_names(names_raw, limit=3)

            # Always provide legacy score
            comp_score_fn = getattr(comp_mod, "get_top_competitor_score", None)
            comp_score = _extract_score(
                await _maybe_call(comp_score_fn, diag, **shared_args),
                default=0,
                diag=diag
            )

            # -------------------------------------------------
            # 6) Final Grade
            # -------------------------------------------------
            overall, grade = compute_grade(seo_score, perf_score, comp_score)

            # -------------------------------------------------
            # 7) Chart Data (kept stable for HTML)
            # -------------------------------------------------
            bar_data = {
                "labels": ["SEO", "Speed", "Security", "AI"],
                "datasets": [{
                    "label": "Scores",
                    "data": [seo_score, perf_score, 90, 95],
                    "backgroundColor": [
                        "rgba(255, 215, 0, 0.8)",
                        "rgba(59, 130, 246, 0.8)",
                        "rgba(16, 185, 129, 0.8)",
                        "rgba(147, 51, 234, 0.8)",
                    ],
                    "borderColor": [
                        "rgba(255, 215, 0, 1)",
                        "rgba(59, 130, 246, 1)",
                        "rgba(16, 185, 129, 1)",
                        "rgba(147, 51, 234, 1)",
                    ],
                    "borderWidth": 1
                }]
            }

            doughnut_data = {
                "labels": ["Healthy", "Warning", "Broken"],
                "datasets": [{
                    "data": [
                        int(links_data.get("internal_links_count", 0)),
                        int(links_data.get("warning_links_count", 0)),
                        int(links_data.get("broken_internal_links", 0)),
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
                    "borderWidth": 1
                }]
            }

            # -------------------------------------------------
            # 8) Final Output (EXACT for HTML; extras are safe)
            # -------------------------------------------------
            final_payload = {
                "overall_score": overall,
                "grade": grade,
                "breakdown": {
                    "seo": seo_score,
                    "performance": {
                        "lcp_ms": lcp_ms,
                        "score": perf_score,
                        "extras": perf_extras
                    },
                    "competitors": {
                        "top_competitor_score": comp_score,
                        "names": comp_names,     # optional, non-breaking
                        "items": comp_items or []  # optional, non-breaking
                    },
                    "links": links_data
                },
                "chart_data": {
                    "bar": bar_data,
                    "doughnut": doughnut_data
                },
                "finished": True
            }

            if AUDIT_DEBUG:
                final_payload["debug"] = {"trace": diag}

            await callback(final_payload)

            # -------------------------------------------------
            # 9) Persist (keys unchanged for storage)
            # -------------------------------------------------
            save_audit_record(self.url, {
                "seo": seo_score,
                "performance": perf_score,
                "competitor": comp_score,
                "links": links_data,
                "overall": overall,
                "grade": grade,
                "lcp_ms": lcp_ms,
                "competitor_names": comp_names
            })

        except Exception as e:
            err_payload = {"error": f"Runner Error: {e}", "finished": True}
            if AUDIT_DEBUG:
                err_payload["debug"] = {"trace": diag}
            await callback(err_payload)
