# app/audit/runner.py
import os
import time
import inspect
import asyncio
import pkgutil
from importlib import import_module
from typing import Any, Dict, Callable, Awaitable, Optional, List, Tuple

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
# Environment Flags
# ============================================================

def _env_flag(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")

AUDIT_DEBUG = _env_flag("AUDIT_DEBUG", False)
AUDIT_DISCOVER_PLUGINS = _env_flag("AUDIT_DISCOVER_PLUGINS", True)  # auto-discover extra analyzers


# ============================================================
# Diagnostics
# ============================================================

def _log_debug(diag: List[str], msg: str):
    if AUDIT_DEBUG:
        diag.append(msg)


# ============================================================
# Flexible Call Utilities
# ============================================================

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


# ============================================================
# Data Normalization / Extraction
# ============================================================

def _extract_score(raw: Any, default: int = 0, diag: Optional[List[str]] = None) -> int:
    """
    Extract an integer-like score from varied return shapes:
    - int / float
    - dict → 'score'|'value'|'total'|'overall' (or nested under 'metrics'/'data' etc.)
    - list/tuple → first item that yields a score
    """
    if raw is None:
        return default

    if isinstance(raw, (int, float)):
        return int(round(float(raw)))

    if isinstance(raw, dict):
        for k in ("score", "value", "total", "overall"):
            if k in raw:
                try:
                    return int(round(float(raw[k])))
                except Exception:
                    pass
        for parent in ("metrics", "data", "result", "summary", "details"):
            if parent in raw and isinstance(raw[parent], dict):
                v = _extract_score(raw[parent], None, diag)
                if v is not None:
                    return v
        # scan nested values
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
        # direct map
        for k in list(base.keys()):
            v = links_raw.get(k)
            if isinstance(v, (int, float)):
                base[k] = int(v)
        # alternative keys
        alt_map = {
            "internal": "internal_links_count",
            "external": "external_links_count",
            "warnings": "warning_links_count",
            "broken": "broken_internal_links",
            "broken_links": "broken_internal_links",
        }
        for src, dest in alt_map.items():
            if base[dest] == 0 and src in links_raw:
                try:
                    base[dest] = int(links_raw[src])
                except Exception:
                    pass
        return base

    if isinstance(links_raw, (list, tuple)):
        for item in links_raw:
            if isinstance(item, dict):
                d = _normalize_links(item)
                for k in base:
                    base[k] = base[k] or d.get(k, 0)
        return base

    return base

def _flatten_scalars(obj: Any, prefix: str = "", max_items: int = 50) -> List[Tuple[str, Any]]:
    """
    Flatten nested dicts/lists into ('key.path', scalar) pairs for HTML display.
    Keeps only scalars (int/float/bool/short str).
    """
    out: List[Tuple[str, Any]] = []

    def _is_scalar(v: Any) -> bool:
        if isinstance(v, (int, float, bool)):
            return True
        if isinstance(v, str):
            return len(v) <= 200
        return False

    def _walk(o: Any, p: str):
        if len(out) >= max_items:
            return
        if isinstance(o, dict):
            for k, v in o.items():
                _walk(v, f"{p}.{k}" if p else str(k))
        elif isinstance(o, (list, tuple)):
            for i, v in enumerate(o):
                _walk(v, f"{p}[{i}]")
        else:
            if _is_scalar(o):
                out.append((p, o))

    _walk(obj, prefix)
    return out[:max_items]

def _kv_to_cards(kv: List[Tuple[str, Any]], top_n: int = 8) -> List[Dict[str, Any]]:
    """
    Convert flattened KV pairs into generic 'cards' for HTML:
    [{'title': 'lcp_ms', 'value': 1234, 'unit': 'ms'}]
    """
    cards: List[Dict[str, Any]] = []

    def unit_for(key: str, val: Any) -> Optional[str]:
        k = key.lower()
        if any(t in k for t in ("ms", "millis", "ttfb", "lcp", "fcp", "tti", "fid")):
            return "ms"
        if any(t in k for t in ("kb", "kib")):
            return "KB"
        if any(t in k for t in ("mb", "mib", "megabytes", "page_size")):
            return "MB"
        if any(t in k for t in ("cls", "ratio", "score", "grade")):
            return None
        if isinstance(val, bool):
            return None
        return None

    # Prefer numeric values first
    nums = [(k, v) for k, v in kv if isinstance(v, (int, float))]
    others = [(k, v) for k, v in kv if not isinstance(v, (int, float))]
    ordered = nums + others

    for k, v in ordered[:top_n]:
        cards.append({"title": k, "value": v, "unit": unit_for(k, v)})
    return cards


# ============================================================
# Optional Plugin Discovery
# ============================================================

def _discover_plugin_callables(diag: List[str]) -> List[Tuple[str, Callable]]:
    """
    Find extra analyzer callables under app.audit.*:
    - Modules whose name contains 'analyzer' or 'plugin'
    - Functions named like: analyze_*, run_*, compute_*
    Returns a list of (display_name, callable) pairs.
    """
    results: List[Tuple[str, Callable]] = []
    try:
        import app.audit as audit_pkg  # type: ignore
        pkg_iter = pkgutil.iter_modules(audit_pkg.__path__, audit_pkg.__name__ + ".")
        for finder, name, ispkg in pkg_iter:
            lower = name.lower()
            if any(tok in lower for tok in ("analyzer", "plugin")) and not ispkg:
                try:
                    mod = import_module(name)
                    for fn_name, fn in inspect.getmembers(mod, callable):
                        if any(fn_name.lower().startswith(p) for p in ("analyze_", "run_", "compute_")):
                            results.append((f"{name}.{fn_name}", fn))
                except Exception as e:
                    _log_debug(diag, f"Plugin import failed for {name}: {e}")
    except Exception as e:
        _log_debug(diag, f"Plugin discovery skipped: {e}")
    return results


# ============================================================
# Main Runner
# ============================================================

class WebsiteAuditRunner:
    """
    Super-flexible runner:
    - Accepts changing analyzer signatures (url/html/soup/lcp_ms/etc.)
    - Handles sync/async seamlessly
    - Normalizes outputs to a stable payload for HTML
    - Adds 'dynamic' sections (cards + kv) so HTML can render ANY new data
    - Optionally discovers and runs extra plugins
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

            shared_args = {"url": self.url, "html": html, "soup": soup, "lcp_ms": lcp_ms}

            # -------------------------------------------------
            # 2) Prepare analyzer callables (with fallbacks)
            # -------------------------------------------------
            # Performance
            perf_fn = getattr(perf_mod, "calculate_performance_score", None)
            if not callable(perf_fn):
                for name, fn in inspect.getmembers(perf_mod, callable):
                    if any(t in name.lower() for t in ("perf", "speed")):
                        perf_fn = fn
                        break

            # SEO
            seo_fn = getattr(seo_mod, "calculate_seo_score", None)
            if not callable(seo_fn):
                for name, fn in inspect.getmembers(seo_mod, callable):
                    if "seo" in name.lower():
                        seo_fn = fn
                        break

            # Links
            links_fn = getattr(links_mod, "analyze_links_async", None)
            if not callable(links_fn):
                for name, fn in inspect.getmembers(links_mod, callable):
                    if "link" in name.lower():
                        links_fn = fn
                        break

            # Competitors
            comp_items_fn = getattr(comp_mod, "get_competitors_with_scores", None)
            comp_names_fn = getattr(comp_mod, "get_competitors", None)
            comp_score_fn = getattr(comp_mod, "get_top_competitor_score", None)

            # Optional plugins
            plugins: List[Tuple[str, Callable]] = _discover_plugin_callables(diag) if AUDIT_DISCOVER_PLUGINS else []

            # -------------------------------------------------
            # 3) Run analyzers concurrently
            # -------------------------------------------------
            await callback({"status": "⚡ Running analyzers...", "crawl_progress": 35})

            async def call(fn: Optional[Callable]) -> Any:
                return await _maybe_call(fn, diag, **shared_args)

            tasks = {
                "perf": asyncio.create_task(call(perf_fn)),
                "seo": asyncio.create_task(call(seo_fn)),
                "links": asyncio.create_task(call(links_fn)),
                "comp_items": asyncio.create_task(call(comp_items_fn)) if callable(comp_items_fn) else None,
                "comp_names": asyncio.create_task(call(comp_names_fn)) if callable(comp_names_fn) else None,
                "comp_score": asyncio.create_task(call(comp_score_fn)) if callable(comp_score_fn) else None,
            }

            # Plugins
            plugin_tasks: Dict[str, asyncio.Task] = {}
            for display, fn in plugins:
                plugin_tasks[display] = asyncio.create_task(call(fn))

            # Await core tasks
            perf_raw = await tasks["perf"]
            seo_raw = await tasks["seo"]
            links_raw = await tasks["links"]
            comp_items_raw = await tasks["comp_items"] if tasks.get("comp_items") else None
            comp_names_raw = await tasks["comp_names"] if tasks.get("comp_names") else None
            comp_score_raw = await tasks["comp_score"] if tasks.get("comp_score") else None

            # Await plugins
            plugin_results: Dict[str, Any] = {}
            for display, t in plugin_tasks.items():
                try:
                    plugin_results[display] = await t
                except Exception as e:
                    _log_debug(diag, f"Plugin task failed for {display}: {e}")

            # -------------------------------------------------
            # 4) Normalize outputs
            # -------------------------------------------------
            await callback({"status": "📊 Normalizing results...", "crawl_progress": 60})

            perf_score = _extract_score(perf_raw, default=0, diag=diag)
            perf_extras = perf_raw if isinstance(perf_raw, dict) else {"raw": perf_raw}

            seo_score = _extract_score(seo_raw, default=0, diag=diag)
            seo_extras = seo_raw if isinstance(seo_raw, dict) else {"raw": seo_raw}

            links_data = _normalize_links(links_raw)

            comp_names = _coerce_names(comp_items_raw, 3) or _coerce_names(comp_names_raw, 3)
            comp_score = _extract_score(comp_score_raw, default=0, diag=diag)

            # -------------------------------------------------
            # 5) Final grade (stable)
            # -------------------------------------------------
            overall, grade = compute_grade(seo_score, perf_score, comp_score)

            # -------------------------------------------------
            # 6) Chart data (stable)
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
            # 7) Dynamic HTML blocks (generic cards + kv for ANY data)
            # -------------------------------------------------
            dynamic: Dict[str, Any] = {
                "cards": [],      # generic cards your HTML can loop over
                "kv": {},         # per-section key/value pairs
                "plugins": {}     # plugin results exposed the same way
            }

            # Core sections to cards/kv
            perf_kv = _flatten_scalars(perf_extras, prefix="performance", max_items=50)
            seo_kv = _flatten_scalars(seo_extras, prefix="seo", max_items=50)
            links_kv = _flatten_scalars(links_data, prefix="links", max_items=50)
            comp_struct = {
                "top_competitor_score": comp_score,
                "names": comp_names,
                "items": comp_items_raw if isinstance(comp_items_raw, list) else []
            }
            comp_kv = _flatten_scalars(comp_struct, prefix="competitors", max_items=50)

            dynamic["kv"]["performance"] = [{"key": k, "value": v} for k, v in perf_kv]
            dynamic["kv"]["seo"] = [{"key": k, "value": v} for k, v in seo_kv]
            dynamic["kv"]["links"] = [{"key": k, "value": v} for k, v in links_kv]
            dynamic["kv"]["competitors"] = [{"key": k, "value": v} for k, v in comp_kv]

            dynamic["cards"].extend(_kv_to_cards(perf_kv, top_n=6))
            dynamic["cards"].extend(_kv_to_cards(seo_kv, top_n=4))
            dynamic["cards"].extend(_kv_to_cards(links_kv, top_n=4))
            dynamic["cards"].extend(_kv_to_cards([("competitors.top_competitor_score", comp_score)], top_n=1))

            # Plugins → kv + cards
            for display_name, result in plugin_results.items():
                kv = _flatten_scalars(result, prefix=display_name, max_items=50)
                dynamic["plugins"][display_name] = {
                    "kv": [{"key": k, "value": v} for k, v in kv],
                    "cards": _kv_to_cards(kv, top_n=6),
                }
                # Also surface a few plugin cards at top-level
                dynamic["cards"].extend(_kv_to_cards(kv, top_n=3))

            # -------------------------------------------------
            # 8) Final Output (stable + dynamic)
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
                        "names": comp_names,
                        "items": comp_items_raw if isinstance(comp_items_raw, list) else []
                    },
                    "links": links_data
                },
                "chart_data": {
                    "bar": bar_data,
                    "doughnut": doughnut_data
                },
                # NEW: generic, forward-compatible blocks for your HTML to render
                "dynamic": dynamic,
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
