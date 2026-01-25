
# app/audit/grader.py
from typing import Dict, Tuple, Optional, Any, Mapping, Iterable
import re

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

MAX_PAGES = 20          # used for coverage percentage
MAX_HTML_BYTES = 200_000  # cap per page to avoid heavy regex work

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

# Real HTML tag patterns (not &lt; &gt;)
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
    """
    Accepts dict-of-html, list-of-html, or anything iterable of HTML-ish items.
    """
    if isinstance(raw_pages, Mapping):
        for v in raw_pages.values():
            yield _to_html(v)
    elif isinstance(raw_pages, (list, tuple, set)):
        for v in raw_pages:
            yield _to_html(v)
    else:
        # Unknown shape; nothing to iterate
        return

def _count_pages(raw_pages: Any) -> int:
    if isinstance(raw_pages, Mapping):
        return len(raw_pages)
    if isinstance(raw_pages, (list, tuple, set)):
        return len(raw_pages)
    return 0

def _as_count(x: Any) -> int:
    """
    Convert broken_links/errors to counts if they are list/dict/etc.
    """
    try:
        if isinstance(x, (list, tuple, set, dict)):
            return len(x)
        if isinstance(x, (int, float)):
            return int(x)
        if x is None:
            return 0
        # e.g., string "3"
        return int(str(x).strip() or 0)
    except Exception:
        return 0

def _sum_internal_links(internal_links: Any) -> int:
    """
    Accept dict-of-lists/sets, list/tuple, dict-of-counts, or a single int.
    """
    try:
        if isinstance(internal_links, Mapping):
            total = 0
            for v in internal_links.values():
                if isinstance(v, (list, tuple, set)):
                    total += len(v)
                elif isinstance(v, Mapping):
                    total += len(v)
                elif isinstance(v, (int, float)):
                    total += int(v)
                elif isinstance(v, str):
                    total += 1 if v else 0
            return total
        if isinstance(internal_links, (list, tuple, set)):
            return len(internal_links)
        if isinstance(internal_links, (int, float)):
            return int(internal_links)
        return 0
    except Exception:
        return 0

def compute_scores(
    lighthouse: Optional[Dict[str, Optional[float]]],  # unused here; Python-only mode
    crawl: Dict[str, Any],
) -> Tuple[float, str, Dict[str, Optional[float]]]:
    """
    Compute website audit using Python heuristics only.
    Inputs:
      - crawl: {
          pages, broken_links, errors, internal_links, external_links, html_content (optional)
        }
    Returns:
      - overall (0..100)
      - letter grade
      - detailed breakdown for dashboards
    """
    try:
        # --- SEO score (titles + meta descriptions presence) ---
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

        total_for_seo = total_for_seo or 1  # avoid zero-div
        seo_score = ((title_count / total_for_seo) * 50.0 +
                     (desc_count / total_for_seo) * 50.0)
        seo_score = clamp(seo_score)

        # --- Performance score (heuristic: fewer broken links -> better) ---
        broken_links = _as_count(crawl.get("broken_links", 0))
        perf_score = clamp(100.0 - broken_links * 5.0)

        # --- Coverage ---
        discovered_pages = _count_pages(raw_pages)
        coverage = clamp((discovered_pages / MAX_PAGES) * 100.0)

        # --- Technical health (heuristic: internal link richness) ---
        internal_total = _sum_internal_links(crawl.get("internal_links", {}))
        ideal_links = max(1, (total_for_seo) * 10)  # 10 links/page ideal
        internal_link_ratio = internal_total / ideal_links
        technical = clamp(internal_link_ratio * 100.0)

        # --- Stability (heuristic: fewer crawl errors -> better) ---
        errors = _as_count(crawl.get("errors", 0))
        stability = clamp(100.0 - errors * 5.0)

        # --- Weighted overall score ---
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

        breakdown: Dict[str, Optional[float]] = {
            "performance": round(perf_score, 1),
            "seo": round(seo_score, 1),
            "coverage": round(coverage, 1),
            "technical": round(technical, 1),
            "stability": round(stability, 1),
            "broken_links": broken_links,
            "errors": errors,
            "missing": {
                "performance": False, "seo": False, "coverage": False,
                "technical": False, "stability": False
            },
        }
        return overall, grade(overall), breakdown

    except Exception as e:
        # NEVER bubble up -> return safe defaults so the API returns and the UI doesn't spin
        breakdown: Dict[str, Optional[float]] = {
            "performance": 0.0,
            "seo": 0.0,
            "coverage": 0.0,
            "technical": 0.0,
            "stability": 0.0,
            "broken_links": 0,
            "errors": 0,
            "missing": {
                "performance": True, "seo": True, "coverage": True,
                "technical": True, "stability": True
            },
            "reason": f"grader_error: {type(e).__name__}",
        }
        return 0.0, "D", breakdown
