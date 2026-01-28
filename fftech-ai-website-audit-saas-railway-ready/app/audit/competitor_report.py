# app/audit/competitor_report.py

"""
Enhanced Competitor Analysis Engine (Lightweight & Deterministic)

⚡ Keeps the original API EXACTLY the same:
   - get_top_competitor_score(url: str) -> int  (unchanged)

🆕 Additionally:
   - Automatically computes top competitor NAMES (deterministic; no HTTP)
   - Builds a full comparison: per-factor components, rankings, winner, summary
   - Exposes a read-only accessor: get_last_competitor_details() -> dict

🔒 Offline-safe (no external HTTP calls).

🎯 Primary Output (unchanged): integer between 70–95 for UI compatibility.

The algorithm simulates:
- Market authority (domain-age proxy)
- Website/brand industry competitiveness
- Content depth signals (name readability proxy)
- Brand trust factors (deterministic)
- Technical confidence score (deterministic)
"""

from __future__ import annotations

import hashlib
import math
from typing import Dict, List, Optional

# --------------------------------------------------------------------
# Internal state (read-only via getter)
# --------------------------------------------------------------------
_LAST_DETAILS: Dict = {}  # populated on each call to get_top_competitor_score(url)


# --------------------------------------------------------------------
# Utilities (deterministic; no I/O)
# --------------------------------------------------------------------
def _normalize_url(url: str) -> str:
    return (url or "").strip().lower()


def _seed_from(text: str) -> int:
    return int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16)


def _extract_domain(url: str) -> str:
    s = _normalize_url(url)
    host = s.split("//")[-1].split("/")[0]
    return host


def _tld_of(url: str) -> str:
    host = _extract_domain(url)
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])  # e.g., example.com / example.com.pk
    return "example.com"


# Industry -> typical competitor brand pools
_INDUSTRY_COMP_MAP: Dict[str, List[str]] = {
    # Appliances / Electronics (Pakistan-leaning examples)
    "haier": ["Dawlance", "PEL", "Orient", "Gree"],
    "appliance": ["LG", "Samsung", "Hisense", "Midea", "Whirlpool"],
    "electronics": ["LG", "Samsung", "Sony", "Panasonic", "TCL"],
    "ac": ["Gree", "Orient", "Kenwood", "Daikin"],
    "fridge": ["Haier", "Samsung", "LG", "Dawlance", "PEL"],

    # General web niches (for other domains)
    "tech": ["Apple", "Samsung", "Google", "Microsoft"],
    "ai": ["OpenAI", "Anthropic", "Cohere", "Google DeepMind"],
    "shop": ["Daraz", "OLX", "Homeshopping"],
    "store": ["Daraz", "OLX", "Homeshopping"],
    "news": ["Dawn", "Geo News", "The News"],
    "blog": ["Medium", "WordPress", "Blogger"],
    "agency": ["Ogilvy", "Dentsu", "Publicis"],
    "finance": ["HBL", "UBL", "MCB", "Meezan Bank", "Allied Bank"],
    "crypto": ["Binance", "OKX", "Coinbase"],
    "health": ["Marham", "Zocdoc", "Practo"],
    "travel": ["Booking.com", "Trip.com", "Expedia", "Skyscanner"],
}


def _guess_tokens(url: str) -> List[str]:
    """
    Extract coarse industry tokens from URL; fallback to 'electronics'.
    """
    s = _normalize_url(url)
    tokens: List[str] = []
    for k in _INDUSTRY_COMP_MAP.keys():
        if k in s:
            tokens.append(k)
    if not tokens:
        # Try basic heuristics from domain words
        domain = _extract_domain(url)
        for k in _INDUSTRY_COMP_MAP.keys():
            if k in domain:
                tokens.append(k)
    return tokens or ["electronics"]


def _rotate_pool(pool: List[str], seed: int) -> List[str]:
    """Deterministic rotation of a list by seed."""
    if not pool:
        return pool
    idx = seed % len(pool)
    return pool[idx:] + pool[:idx]


def _domain_age_score_from_name(name: str) -> int:
    """
    Simulate domain age/authority using branded length.
    Shorter names -> higher score. Clamp 5–20.
    """
    domain_length = len(name)
    val = max(0, 30 - domain_length)
    return max(5, min(val, 20))


def _industry_score_for(url_or_name: str) -> int:
    """
    Token-based industry competitiveness score; clamp to max 25.
    """
    s = _normalize_url(url_or_name)
    base = 10
    for word, val in {
        "tech": 18, "ai": 20, "shop": 15, "store": 15, "news": 17,
        "blog": 10, "agency": 14, "finance": 20, "crypto": 12,
        "health": 18, "travel": 16, "appliance": 18, "electronics": 18,
        "haier": 18, "ac": 16, "fridge": 16, "cool": 12
    }.items():
        if word in s:
            base += val
            break
    return min(base, 25)


def _brand_score(seed: int) -> float:
    raw = (seed % 1000) / 1000.0
    return 10 + (raw * 10)  # 10–20


def _content_score_from_name(text: str) -> int:
    vowels = sum(1 for c in text.lower() if c in "aeiou")
    return min(20, 8 + vowels)  # 8..20


def _technical_score(seed: int) -> int:
    return 15 + ((seed >> 8) % 10)  # 15–24


def _score_components(key: str) -> Dict[str, float]:
    """
    Build a component breakdown for a given key (URL or competitor name).
    """
    seed = _seed_from(key)
    domain_age = _domain_age_score_from_name(key)
    industry = _industry_score_for(key)
    brand = _brand_score(seed)
    content = _content_score_from_name(key)
    technical = _technical_score(seed)
    return {
        "domain_age": float(domain_age),
        "industry": float(industry),
        "brand": float(brand),
        "content": float(content),
        "technical": float(technical),
    }


def _weighted_total(components: Dict[str, float]) -> float:
    return (
        components["domain_age"] * 0.20
        + components["industry"] * 0.20
        + components["brand"] * 0.25
        + components["content"] * 0.15
        + components["technical"] * 0.20
    )


def _scale_to_ui_range(weighted: float) -> int:
    # Keep the original UI range: 70–95
    return int(70 + (int(weighted) % 26))


def _pick_competitors(url: str, top_n: int = 3) -> List[str]:
    """
    Deterministically pick competitor brand names from the token pools.
    Avoid returning the obvious self-brand token if present in pool.
    """
    tokens = _guess_tokens(url)
    seed = _seed_from(_normalize_url(url))
    pool: List[str] = []
    for t in tokens:
        pool.extend(_INDUSTRY_COMP_MAP.get(t, []))

    # Deduplicate while preserving order
    seen = set()
    pool = [x for x in pool if not (x in seen or seen.add(x))]

    if not pool:
        pool = ["Contoso", "Northwind", "Fabrikam", "AdventureWorks"]

    rotated = _rotate_pool(pool, seed)
    # If a token equals a brand name, exclude it from the final list
    excludes = set(tokens)
    filtered = [p for p in rotated if p.lower() not in excludes]
    if not filtered:
        filtered = rotated
    return filtered[:max(1, top_n)]


def _human_summary(target_score: int, comps: List[Dict[str, int]]) -> str:
    """
    Produce a small, human-friendly comparison summary.
    """
    if not comps:
        return "No competitors inferred; baseline score computed."
    leader = max(comps, key=lambda x: x.get("score", 0))
    gap = leader["score"] - target_score
    if gap > 0:
        return (
            f"Top competitor is {leader['name']} ({leader['score']}). "
            f"They lead by {gap} points. Focus on technical and brand signals to close the gap."
        )
    elif gap < 0:
        return (
            f"You lead with {target_score}. Nearest competitor is "
            f"{leader['name']} at {leader['score']}. Maintain content freshness and performance."
        )
    else:
        return (
            f"Scores are tied at {target_score}. Differentiate using Core Web Vitals and structured data."
        )


# --------------------------------------------------------------------
# PUBLIC: Original function (UNCHANGED signature & return)
# --------------------------------------------------------------------
def get_top_competitor_score(url: str) -> int:
    """
    Generate a realistic competitor score using deterministic heuristics
    while matching the original return signature.

    The score range remains 70–95 for UI compatibility.
    Additionally, this call populates a rich, read-only comparison object
    retrievable via get_last_competitor_details().
    """
    # Normalize URL and derive base components
    clean_url = _normalize_url(url)
    domain = _extract_domain(clean_url)
    seed = _seed_from(clean_url)

    # --- Original component logic (kept compatible) ---
    domain_length = len(domain)
    domain_age_score = max(5, min(max(0, 30 - domain_length), 20))  # 5–20
    industry_score = _industry_score_for(clean_url)                  # <= 25
    brand_score = _brand_score(seed)                                 # 10–20
    vowels = sum(1 for c in clean_url if c in "aeiou")
    content_score = min(20, 8 + vowels)                              # 8–20
    technical_score = 15 + ((seed >> 8) % 10)                        # 15–24

    weighted = (
        (domain_age_score * 0.20)
        + (industry_score * 0.20)
        + (brand_score * 0.25)
        + (content_score * 0.15)
        + (technical_score * 0.20)
    )
    final_score = _scale_to_ui_range(weighted)  # 70–95 (unchanged)

    # --- NEW: Build a complete deterministic competitor comparison ---
    # 1) Target breakdown
    target_components = {
        "domain_age": float(domain_age_score),
        "industry": float(industry_score),
        "brand": float(brand_score),
        "content": float(content_score),
        "technical": float(technical_score),
    }

    # 2) Pick top 3 competitor names
    comp_names = _pick_competitors(clean_url, top_n=3)

    # 3) Score each competitor with the SAME rubric
    comp_items: List[Dict[str, int]] = []
    comp_detailed: List[Dict] = []
    for i, name in enumerate(comp_names):
        # Key used to seed and compute components
        key = f"{name.lower()}:{_tld_of(clean_url)}"
        comps = _score_components(key)
        score = _scale_to_ui_range(_weighted_total(comps))

        comp_items.append({"name": name, "score": int(score)})
        comp_detailed.append({
            "name": name,
            "components": comps,
            "score": int(score),
        })

    # 4) Rankings + deltas
    sorted_all = sorted(
        [{"name": "You", "score": int(final_score)}] + comp_items,
        key=lambda x: x["score"],
        reverse=True
    )
    leader = sorted_all[0]
    deltas = [
        {
            "vs": item["name"],
            "delta": int(final_score) - int(item["score"])
        }
        for item in comp_items
    ]

    # 5) Natural-language summary
    summary = _human_summary(final_score, comp_items)

    # 6) Persist to module-level (read-only via getter)
    global _LAST_DETAILS
    _LAST_DETAILS = {
        "url": clean_url,
        "target": {
            "domain": domain,
            "score": int(final_score),
            "components": target_components,
        },
        "competitors": {
            "names": comp_names,
            "items": comp_items,           # [{name, score}]
            "detailed": comp_detailed,     # [{name, components{...}, score}]
        },
        "rankings": sorted_all,            # sorted by score desc
        "deltas": deltas,                  # target minus competitor
        "summary": summary,
        "weights": {
            "domain_age": 0.20,
            "industry": 0.20,
            "brand": 0.25,
            "content": 0.15,
            "technical": 0.20,
        },
        "notes": "Deterministic offline comparison; no external calls.",
    }

    return int(final_score)


# --------------------------------------------------------------------
# PUBLIC (optional): Read the latest comparison (no I/O change to original)
# --------------------------------------------------------------------
def get_last_competitor_details() -> Dict:
    """
    Returns the last computed competitor details produced by
    get_top_competitor_score(url). If called before any scoring,
    returns {}.
    """
    # Return a shallow copy to discourage in-place mutation by callers
    return dict(_LAST_DETAILS)
