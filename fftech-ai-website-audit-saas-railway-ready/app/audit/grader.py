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
    return str(x)[:MAX_HTML_BYTES]

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
    if isinstance(x, (list, tuple, set, dict)):
        return len(x)
    if isinstance(x, (int, float)):
        return int(x)
    return 0

def _sum_internal_links(internal_links: Any) -> int:
    if isinstance(internal_links, Mapping):
        return sum(len(v) for v in internal_links.values() if isinstance(v, (list, set, tuple)))
    if isinstance(internal_links, (list, set, tuple)):
        return len(internal_links)
    if isinstance(internal_links, int):
        return internal_links
    return 0


def compute_scores(
    lighthouse: Optional[Dict[str, Optional[float]]],
    crawl: Dict[str, Any],
) -> Tuple[float, str, Dict[str, Optional[float]]]:

    try:
        pages = crawl.get("pages", {})
        errors = _as_count(crawl.get("errors", []))

        # ✅ FIX: support both old and new crawler keys
        broken_links = _as_count(
            crawl.get("broken_links")
            or crawl.get("broken_internal")
            or []
        )

        # --- SEO ---
        total_pages = 0
        title_count = 0
        desc_count = 0

        for html in _iter_pages(pages):
            total_pages += 1
            if TAG_TITLE.search(html):
                title_count += 1
            if TAG_META_DESC.search(html):
                desc_count += 1

        total_pages = total_pages or 1
        seo_score = clamp(
            (title_count / total_pages) * 50 +
            (desc_count / total_pages) * 50
        )

        # --- Performance ---
        performance = clamp(100 - broken_links * 5)

        # --- Coverage ---
        coverage = clamp((_count_pages(pages) / MAX_PAGES) * 100)

        # --- Technical ---
        internal_links = crawl.get("internal_links", {})
        internal_total = _sum_internal_links(internal_links)
        ideal_links = max(1, total_pages * 10)
        technical = clamp((internal_total / ideal_links) * 100)

        # --- Stability ---
        stability = clamp(100 - errors * 5)

        # --- Weighted score ---
        weighted = (
            performance * WEIGHTS["performance"] +
            seo_score * WEIGHTS["seo"] +
            coverage * WEIGHTS["coverage"] +
            technical * WEIGHTS["technical"] +
            stability * WEIGHTS["stability"]
        )
        overall = clamp(round(weighted, 1))

        breakdown = {
            "performance": round(performance, 1),
            "seo": round(seo_score, 1),
            "coverage": round(coverage, 1),
            "technical": round(technical, 1),
            "stability": round(stability, 1),
            "broken_links": broken_links,
            "errors": errors,
            "missing": {
                "performance": False,
                "seo": False,
                "coverage": False,
                "technical": False,
                "stability": False,
            },
        }

        return overall, grade(overall), breakdown

    except Exception as e:
        return 0.0, "D", {
            "performance": 0,
            "seo": 0,
            "coverage": 0,
            "technical": 0,
            "stability": 0,
            "broken_links": 0,
            "errors": 0,
            "missing": {
                "performance": True,
                "seo": True,
                "coverage": True,
                "technical": True,
                "stability": True,
            },
            "reason": str(e),
        }
