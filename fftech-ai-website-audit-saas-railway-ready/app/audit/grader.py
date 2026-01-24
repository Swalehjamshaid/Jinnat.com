# app/audit/grader.py
from typing import Dict, Tuple, Optional
from urllib.parse import urlparse
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

MAX_PAGES = 20  # used for coverage percentage

def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))

def grade(score: float) -> str:
    for cutoff, letter in GRADE_BANDS:
        if score >= cutoff:
            return letter
    return "D"

def _safe_clamp(v: Optional[float]) -> Optional[float]:
    return None if v is None else clamp(v)

# -----------------------------
# Python-only score estimation
# -----------------------------
def compute_scores(
    lighthouse: Optional[Dict[str, Optional[float]]],  # will be None in Python-only
    crawl: Dict[str, int],
) -> Tuple[float, str, Dict[str, Optional[float]]]:
    """
    Compute website audit using Python heuristics only.
    Inputs:
      - crawl: { pages, broken_links, errors, internal_links, external_links, html_content }
    Returns:
      - overall (0..100)
      - letter grade
      - detailed breakdown for dashboards
    """

    # --- Estimate SEO score ---
    # Heuristic: ratio of pages with <title> and <meta description>
    seo_score = 0
    pages = crawl.get("pages", {})
    total_pages = len(pages) or 1
    title_count, desc_count = 0, 0
    for html in pages.values():
        if re.search(r"<title>.*</title>", html, re.IGNORECASE):
            title_count += 1
        if re.search(r"<meta\s+name=['\"]description['\"].*?>", html, re.IGNORECASE):
            desc_count += 1
    seo_score = ((title_count / total_pages) * 50 + (desc_count / total_pages) * 50)
    seo_score = clamp(seo_score)

    # --- Estimate Performance score ---
    # Heuristic: fewer broken links => higher score
    broken_links = crawl.get("broken_links", 0)
    perf_score = clamp(100 - broken_links * 5)

    # --- Coverage ---
    coverage = clamp((total_pages / MAX_PAGES) * 100)

    # --- Technical health ---
    # Heuristic: ratio of internal links per page
    internal_links = crawl.get("internal_links", {})
    internal_link_ratio = sum(len(v) for v in internal_links.values()) / (total_pages * 10)  # 10 links/page ideal
    technical = clamp(internal_link_ratio * 100)

    # --- Stability ---
    # Heuristic: fewer crawl errors => higher stability
    errors = crawl.get("errors", 0)
    stability = clamp(100 - errors * 5)

    # --- Weighted overall score ---
    components = [perf_score, seo_score, coverage, technical, stability]
    weights = [WEIGHTS["performance"], WEIGHTS["seo"], WEIGHTS["coverage"], WEIGHTS["technical"], WEIGHTS["stability"]]
    weighted_sum = sum(c * w for c, w in zip(components, weights))
    overall = clamp(weighted_sum / sum(weights))

    # --- Apply penalties for broken links and errors ---
    broken_penalty = min(15, broken_links * 2)
    error_penalty  = min(20, errors * 5)
    overall = clamp(round(overall - broken_penalty - error_penalty, 1))

    breakdown: Dict[str, Optional[float]] = {
        "performance": round(perf_score, 1),
        "seo": round(seo_score, 1),
        "coverage": round(coverage, 1),
        "technical": round(technical, 1),
        "stability": round(stability, 1),
        "broken_links": broken_links,
        "errors": errors,
        "missing": { "performance": False, "seo": False, "coverage": False, "technical": False, "stability": False }
    }

    return overall, grade(overall), breakdown
