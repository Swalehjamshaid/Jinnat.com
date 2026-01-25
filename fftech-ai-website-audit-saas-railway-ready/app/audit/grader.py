from typing import Dict, Tuple, Optional, Any, Mapping, Iterable
import re

GRADE_BANDS = ((90, "A+"), (80, "A"), (70, "B"), (60, "C"), (0,  "D"))

WEIGHTS = {"performance": 0.35, "seo": 0.30, "coverage": 0.10, "technical": 0.15, "stability": 0.10}

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
TAG_META_DESC = re.compile(r'<meta\s+name=["\']description["\']\s+content=["\'].*?["\']', re.IGNORECASE | re.DOTALL)

def _to_html(x: Any) -> str:
    if isinstance(x, (bytes, bytearray)):
        return x[:MAX_HTML_BYTES].decode("utf-8", "ignore")
    return str(x)[:MAX_HTML_BYTES]

def _iter_pages(raw_pages: Any) -> Iterable[str]:
    if isinstance(raw_pages, Mapping):
        for v in raw_pages.values(): yield _to_html(v)
    elif isinstance(raw_pages, (list, tuple, set)):
        for v in raw_pages: yield _to_html(v)

def _count_pages(raw_pages: Any) -> int:
    if isinstance(raw_pages, Mapping): return len(raw_pages)
    if isinstance(raw_pages, (list, tuple, set)): return len(raw_pages)
    return 0

def _as_count(x: Any) -> int:
    try:
        if isinstance(x, (list, tuple, set, dict)): return len(x)
        if isinstance(x, (int, float)): return int(x)
        if x is None: return 0
        return int(str(x).strip() or 0)
    except Exception:
        return 0

def _sum_internal_links(internal_links: Any) -> int:
    try:
        if isinstance(internal_links, Mapping):
            return sum(len(v) if isinstance(v, (list, tuple, set)) else int(v) for v in internal_links.values())
        if isinstance(internal_links, (list, tuple, set)): return len(internal_links)
        if isinstance(internal_links, (int, float)): return int(internal_links)
        return 0
    except Exception:
        return 0

def compute_scores(lighthouse: Optional[Dict[str, Optional[float]]], crawl: Dict[str, Any]) -> Tuple[float, str, Dict[str, Optional[float]]]:
    try:
        raw_pages = crawl.get("pages") or {}
        total_for_seo, title_count, desc_count = 0, 0, 0
        for html in _iter_pages(raw_pages):
            total_for_seo += 1
            if TAG_TITLE.search(html): title_count += 1
            if TAG_META_DESC.search(html): desc_count += 1
        total_for_seo = total_for_seo or 1
        seo_score = clamp((title_count / total_for_seo * 50) + (desc_count / total_for_seo * 50))
        broken_links = _as_count(crawl.get("broken_links", 0))
        perf_score = clamp(100 - broken_links * 5)
        discovered_pages = _count_pages(raw_pages)
        coverage = clamp(discovered_pages / MAX_PAGES * 100)
        internal_total = _sum_internal_links(crawl.get("internal_links", {}))
        technical = clamp((internal_total / max(1, total_for_seo * 10)) * 100)
        errors = _as_count(crawl.get("errors", 0))
        stability = clamp(100 - errors * 5)
        weighted_sum = sum(c * w for c, w in zip([perf_score, seo_score, coverage, technical, stability], list(WEIGHTS.values())))
        overall = clamp(weighted_sum / sum(WEIGHTS.values()))
        broken_penalty = min(15.0, broken_links * 2)
        error_penalty = min(20.0, errors * 5)
        overall = clamp(round(overall - broken_penalty - error_penalty, 1))
        breakdown = {"performance": round(perf_score,1),"seo": round(seo_score,1),"coverage": round(coverage,1),"technical": round(technical,1),"stability": round(stability,1),"broken_links": broken_links,"errors": errors,"missing": {"performance":False,"seo":False,"coverage":False,"technical":False,"stability":False}}
        return overall, grade(overall), breakdown
    except Exception as e:
        breakdown = {"performance":0,"seo":0,"coverage":0,"technical":0,"stability":0,"broken_links":0,"errors":0,"missing":{"performance":True,"seo":True,"coverage":True,"technical":True,"stability":True},"reason": str(e)}
        return 0.0,"D",breakdown
