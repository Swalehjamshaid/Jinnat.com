
# app/audit/grader.py
from typing import Dict, Tuple, Optional

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

MAX_PAGES = 20  # used for coverage percentage


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def grade(score: float) -> str:
    for c, g in GRADE_BANDS:
        if score >= c:
            return g
    return "D"


def _opt_clamp(v: Optional[float]) -> Optional[float]:
    return None if v is None else clamp(v)


def compute_scores(
    lighthouse: Dict[str, Optional[float]],
    crawl: Dict[str, int],
) -> Tuple[float, str, Dict[str, float]]:
    """
    Computes the audit score from Lighthouse (may be partial) and crawl stats.
      lighthouse: {
        performance?, seo?, accessibility?, best_practices?,
        lcp?, cls?
      }
      crawl: { pages, broken_links, errors }
    Returns:
      overall (0..100), letter grade, breakdown dict
    """

    # --- Lighthouse Scores (allow None) ---
    perf = _opt_clamp(lighthouse.get("performance"))
    seo  = _opt_clamp(lighthouse.get("seo"))
    acc  = _opt_clamp(lighthouse.get("accessibility"))
    bp   = _opt_clamp(lighthouse.get("best_practices"))

    # --- Coverage ---
    pages = max(0, crawl.get("pages", 0))
    coverage = clamp((pages / MAX_PAGES) * 100)

    # --- Technical Health ---
    tech_vals = [v for v in (acc, bp) if v is not None]
    tech = sum(tech_vals) / len(tech_vals) if tech_vals else 0.0

    # --- Stability (CLS + LCP penalties) ---
    lcp = lighthouse.get("lcp")  # seconds
    cls = lighthouse.get("cls")  # unitless
    lcp_penalty = 0 if (lcp is None or lcp <= 2.5) else min(20, lcp * 3)
    cls_penalty = 0 if (cls is None or cls <= 0.1) else min(20, cls * 100)
    stability = clamp(100 - lcp_penalty - cls_penalty)

    # --- Weighted Score (ignore missing components proportionally) ---
    components = []
    weights = []

    if perf is not None:
        components.append(perf); weights.append(WEIGHTS["performance"])
    if seo is not None:
        components.append(seo); weights.append(WEIGHTS["seo"])

    components.append(coverage); weights.append(WEIGHTS["coverage"])
    components.append(tech);     weights.append(WEIGHTS["technical"])
    components.append(stability);weights.append(WEIGHTS["stability"])

    wsum = sum(weights) if weights else 1.0
    weighted = sum(c * w for c, w in zip(components, weights)) / wsum
    overall = clamp(weighted)

    # --- Penalties from crawl ---
    broken_penalty = min(15, max(0, crawl.get("broken_links", 0)) * 2)
    error_penalty  = min(20, max(0, crawl.get("errors", 0)) * 5)

    overall = clamp(round(overall - broken_penalty - error_penalty, 1))

    # --- Breakdown for dashboard/chart ---
    breakdown = {
        "performance": round(perf, 1) if perf is not None else None,
        "seo": round(seo, 1) if seo is not None else None,
        "coverage": round(coverage, 1),
        "technical": round(tech, 1),
        "stability": round(stability, 1),
        "broken_links": max(0, crawl.get("broken_links", 0)),
        "errors": max(0, crawl.get("errors", 0)),
        "missing": {
            "performance": perf is None,
            "seo": seo is None,
            "accessibility": acc is None,
            "best_practices": bp is None,
            "lcp": lcp is None,
            "cls": cls is None,
        },
        # Removed pseudo-random "confidence" — makes results deterministic and honest.
    }

    return overall, grade(overall), breakdown
