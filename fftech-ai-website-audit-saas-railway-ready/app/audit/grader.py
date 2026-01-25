# app/audit/grader.py
from typing import Dict, Tuple, Optional, Any, Mapping, Iterable
import re
from .links import analyze_links  # NEW: import link analyzer

GRADE_BANDS = (
    (90, "A+"),
    (80, "A"),
    (70, "B"),
    (60, "C"),
    (0,  "D"),
)

# Default weights for each component
WEIGHTS = {
    "performance": 0.35,
    "seo": 0.30,
    "coverage": 0.10,
    "technical": 0.15,
    "stability": 0.10,
}

MAX_PAGES = 20
MAX_HTML_BYTES = 200_000

def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    try:
        return max(lo, min(hi, float(v)))
    except Exception:
        return lo

def grade(score: float) -> str:
    for cutoff, letter in GRADE_BANDS:
        if score >= cutoff:
            return letter
    return "D"

TAG_TITLE = re.compile(r"<title[^>]*>.*?</title>", re.IGNORECASE | re.DOTALL)
TAG_META_DESC = re.compile(
    r'<meta\s+name=["\']description["\']\s+content=["\'].*?["\']',
    re.IGNORECASE | re.DOTALL
)

def _to_html(x: Any) -> str:
    if isinstance(x, (bytes, bytearray)):
        return x[:MAX_HTML_BYTES].decode("utf-8", "ignore")
    s = str(x)
    return s[:MAX_HTML_BYTES]

def _iter_pages(raw_pages: Any) -> Iterable[str]:
    if isinstance(raw_pages, Mapping):
        for v in raw_pages.values():
            yield _to_html(v)
    elif isinstance(raw_pages, (list, tuple, set)):
        for v in raw_pages:
            yield _to_html(v)

def _count_pages(raw_pages: Any) -> int:
    if isinstance(raw_pages, Mapping):
        return len(raw_pages)
    if isinstance(raw_pages, (list, tuple, set)):
        return len(raw_pages)
    return 0

def _as_count(x: Any) -> int:
    try:
        if isinstance(x, (list, tuple, set, dict)):
            return len(x)
        if isinstance(x, (int, float)):
            return int(x)
        if x is None:
            return 0
        return int(str(x).strip() or 0)
    except Exception:
        return 0

def compute_scores(
    lighthouse: Optional[Dict[str, Optional[float]]],
    crawl: Dict[str, Any],
) -> Tuple[float, str, Dict[str, Optional[float]]]:
    """
    Compute website audit scores using Python heuristics + links.py metrics.
    """
    try:
        raw_pages = crawl.get("pages") or {}
        total_for_seo = 0
        title_count = 0
        desc_count = 0

        for html in _iter_pages(raw_pages):
            total_for_seo += 1
            if TAG_TITLE.search(html):
                title_count += 1
            if TAG_META_DESC.search(html):
                desc_count += 1

        total_for_seo = total_for_seo or 1
        seo_score = ((title_count / total_for_seo) * 50.0 +
                     (desc_count / total_for_seo) * 50.0)
        seo_score = clamp(seo_score)

        # --- Use links.py to analyze link data ---
        link_metrics = analyze_links(crawl)

        broken_links = link_metrics.get("total_broken_links", 0)
        total_internal_links = link_metrics.get("total_internal_links", 0)
        total_external_links = link_metrics.get("total_external_links", 0)
        internal_ratio = link_metrics.get("internal_link_ratio", 0)

        # --- Performance score: fewer broken links is better ---
        perf_score = clamp(100.0 - broken_links * 5.0)

        # --- Coverage ---
        discovered_pages = _count_pages(raw_pages)
        coverage = clamp((discovered_pages / MAX_PAGES) * 100.0)

        # --- Technical: internal link richness ---
        ideal_links = max(1, total_for_seo * 10)
        technical = clamp((total_internal_links / ideal_links) * 100.0)

        # --- Stability: fewer crawl errors better ---
        errors = _as_count(crawl.get("errors", 0))
        stability = clamp(100.0 - errors * 5.0)

        # --- Weighted overall ---
        components = [perf_score, seo_score, coverage, technical, stability]
        weights = [
            WEIGHTS["performance"],
            WEIGHTS["seo"],
            WEIGHTS["coverage"],
            WEIGHTS["technical"],
            WEIGHTS["stability"],
        ]
        weighted_sum = sum(c * w for c, w in zip(components, weights))
        overall = clamp(weighted_sum / max(1e-9, sum(weights)))

        # --- Penalties ---
        broken_penalty = min(15.0, broken_links * 2.0)
        error_penalty  = min(20.0, errors * 5.0)
        overall = clamp(round(overall - broken_penalty - error_penalty, 1))

        breakdown = {
            "performance": round(perf_score, 1),
            "seo": round(seo_score, 1),
            "coverage": round(coverage, 1),
            "technical": round(technical, 1),
            "stability": round(stability, 1),
            "broken_links": broken_links,
            "errors": errors,
            "internal_link_ratio": internal_ratio,
            "missing": {
                "performance": False,
                "seo": False,
                "coverage": False,
                "technical": False,
                "stability": False
            },
        }

        return overall, grade(overall), breakdown

    except Exception as e:
        breakdown = {
            "performance": 0.0,
            "seo": 0.0,
            "coverage": 0.0,
            "technical": 0.0,
            "stability": 0.0,
            "broken_links": 0,
            "errors": 0,
            "internal_link_ratio": 0,
            "missing": {
                "performance": True,
                "seo": True,
                "coverage": True,
                "technical": True,
                "stability": True
            },
            "reason": f"grader_error: {type(e).__name__}",
        }
        return 0.0, "D", breakdown
