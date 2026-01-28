"""
World-class Competitor Benchmark Engine (Deterministic & Offline)
───────────────────────────────────────────────────────────────
Public API (unchanged):
  • get_top_competitor_score(url: str) -> int           # 70–95 range
  • get_last_competitor_details() -> dict               # rich comparison

Features:
  • Deterministic: same URL → same score & competitors
  • No external calls: fully offline & instant
  • Real competitor names based on industry heuristics
  • Detailed breakdown (components, rankings, deltas, summary)
  • Human-readable explanation
  • Easy to upgrade to real SERP/Ahrefs data later
"""

from __future__ import annotations
import hashlib
from typing import Dict, List, Optional


# ────────────────────────────────────────────────
# Module-level cache (read-only via getter)
# ────────────────────────────────────────────────
_LAST_DETAILS: Optional[Dict] = None


# ────────────────────────────────────────────────
# Industry → competitor brand pools (expandable)
# ────────────────────────────────────────────────
_COMPETITOR_POOLS: Dict[str, List[str]] = {
    # Pakistan / Appliances
    "haier": ["Dawlance", "PEL", "Orient", "Gree", "Kenwood", "Waves"],
    "appliance": ["LG", "Samsung", "Hisense", "Midea", "Whirlpool"],
    "ac": ["Gree", "Orient", "Kenwood", "Daikin", "Haier"],
    "fridge": ["Haier", "Samsung", "LG", "Dawlance", "PEL"],
    # General / Global
    "tech": ["Apple", "Samsung", "Google", "Microsoft", "Sony"],
    "ai": ["OpenAI", "Anthropic", "Google DeepMind", "xAI", "Meta AI"],
    "ecommerce": ["Daraz", "Amazon", "AliExpress", "OLX", "Homeshopping"],
    "news": ["Dawn", "Geo News", "BBC", "CNN", "Al Jazeera"],
    "finance": ["HBL", "UBL", "MCB", "Meezan Bank", "Bank Alfalah"],
    "crypto": ["Binance", "Coinbase", "Kraken", "OKX", "Bybit"],
    "health": ["Marham", "Sehat Kahani", "Dawaai", "Oladoc"],
    # Fallback generic pool
    "default": ["Contoso", "Northwind", "Fabrikam", "AdventureWorks", "Tailwind"],
}


def _normalize_domain(url: str) -> str:
    """Clean domain/netloc for comparison."""
    s = (url or "").strip().lower()
    host = s.split("//")[-1].split("/")[0].split("?")[0]
    if host.startswith("www."):
        host = host[4:]
    return host.rstrip(".")


def _seed_from(text: str) -> int:
    """Deterministic 64-bit-ish seed from string."""
    return int(hashlib.sha256(text.encode()).hexdigest(), 16)


def _guess_industry_keys(domain: str) -> List[str]:
    """Extract likely industry tokens from domain."""
    domain = domain.lower()
    matches = []
    for key in _COMPETITOR_POOLS:
        if key in domain:
            matches.append(key)
    return matches or ["default"]


def _pick_competitors(industry_keys: List[str], seed: int, top_n: int = 3) -> List[str]:
    """Deterministically select top competitors."""
    pool: List[str] = []
    for key in industry_keys:
        pool.extend(_COMPETITOR_POOLS.get(key, []))

    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for x in pool:
        if x not in seen:
            seen.add(x)
            uniq.append(x)

    if not uniq:
        uniq = _COMPETITOR_POOLS["default"]

    # Deterministic rotation by seed
    idx = seed % len(uniq)
    rotated = uniq[idx:] + uniq[:idx]
    return rotated[:top_n]


def _simulate_brand_score(seed: int) -> int:
    """Brand strength simulation (10–25)."""
    return 10 + (seed % 16)


def _simulate_content_score(domain: str) -> int:
    """Content depth proxy (8–22) based on vowel count."""
    vowels = sum(1 for c in domain.lower() if c in "aeiou")
    return min(22, 8 + vowels * 2)


def _simulate_technical_score(seed: int) -> int:
    """Technical confidence proxy (12–28)."""
    return 12 + ((seed >> 12) % 17)


def _component_breakdown(domain: str, seed: int) -> Dict[str, float]:
    """Breakdown of simulated factors."""
    return {
        "brand": float(_simulate_brand_score(seed)),     # 40%
        "content": float(_simulate_content_score(domain)),  # 30%
        "technical": float(_simulate_technical_score(seed)),# 30%
    }


def _weighted_total(components: Dict[str, float]) -> float:
    """Balanced weighted total."""
    return components["brand"] * 0.40 + components["content"] * 0.30 + components["technical"] * 0.30


def _scale_to_ui_range(raw: float) -> int:
    """Map internal score to UI-friendly 70–95 range."""
    return int(70 + (raw % 26))


def get_top_competitor_score(url: str) -> int:
    """
    Public API – unchanged signature.
    Returns a deterministic competitor benchmark score (70–95).
    Side-effect: populates global _LAST_DETAILS for rich comparison.
    """
    global _LAST_DETAILS

    clean = _normalize_domain(url)
    seed = _seed_from(clean)

    # Target (your site)
    t_components = _component_breakdown(clean, seed)
    t_raw = _weighted_total(t_components)
    t_score = _scale_to_ui_range(t_raw)

    # Competitors
    industry_keys = _guess_industry_keys(clean)
    comp_names = _pick_competitors(industry_keys, seed, top_n=3)

    comps = []
    for name in comp_names:
        c_seed = _seed_from(name + clean)
        c_components = _component_breakdown(name, c_seed)
        c_raw = _weighted_total(c_components)
        c_score = _scale_to_ui_range(c_raw)
        comps.append({
            "name": name,
            "score": c_score,
            "delta": t_score - c_score,
            "components": c_components,
        })

    # Rank DESC
    comps = sorted(comps, key=lambda x: x["score"], reverse=True)
    for i, c in enumerate(comps, start=1):
        c["rank"] = i

    leader = comps[0] if comps else None
    names = [c["name"] for c in comps]

    # Human summary
    if leader:
        gap = leader["score"] - t_score
        if gap > 0:
            summary = f"Leader {leader['name']} outperforms target by {gap} points; close the gap via brand and technical improvements."
        elif gap < 0:
            summary = f"Target outperforms competitors by {abs(gap)} points; maintain lead with content depth gains."
        else:
            summary = f"Target is neck-and-neck with {leader['name']}; small optimization will break the tie."
    else:
        summary = "No competitors identified."

    _LAST_DETAILS = {
        "target": {"domain": clean, "score": t_score, "components": t_components},
        "competitors": comps,
        "leader": leader,
        "names": names,
        "industry_keys": industry_keys,
        "summary": summary,
        "notes": "Offline deterministic benchmark — no external API calls.",
    }
    return t_score


def get_last_competitor_details() -> Dict:
    """Returns the last computed comparison details (shallow copy)."""
    if _LAST_DETAILS is None:
        return {}
    return dict(_LAST_DETAILS)
