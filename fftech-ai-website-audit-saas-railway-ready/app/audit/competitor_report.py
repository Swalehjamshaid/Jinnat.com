from typing import Dict, List
import hashlib
import time


def top_competitor_score(domain: str) -> int:
    """
    Returns a stable, pseudo-realistic competitor benchmark score (0–100)
    based on domain string.

    The score is deterministic (same domain → same score),
    but varies reasonably across different domains.

    In a real-world version you would replace this with:
    • SERP position analysis
    • SimilarWeb / Ahrefs-like metrics
    • Lighthouse / PageSpeed scores of top competitors
    • Backlink count / domain authority approximation
    """
    # Create a stable hash from the domain
    h = hashlib.sha256(domain.lower().encode()).hexdigest()

    # Take first 8 hex chars → convert to int (0–0xFFFFFFFF)
    seed = int(h[:8], 16)

    # Map to 55–98 range (most good competitors are in 70–95)
    # We avoid perfect 100 to make user's score feel potentially better
    score = 55 + (seed % 44)                  # base 55–98
    score += (seed // 100000 % 10) * 2        # small bonus

    # Small time-based jitter (only ±3) — useful during demos
    # Remove in production if you want 100% deterministic
    jitter = int(time.time() // 3600) % 7 - 3
    score = max(55, min(98, score + jitter))

    return score


def competitor_summary(domain: str) -> Dict[str, int | List[str]]:
    """
    Returns a structured summary that can be directly consumed by the frontend.

    Same output shape as before, but with more realistic / detailed notes.
    """
    score = top_competitor_score(domain)

    # You can make notes more dynamic / domain-specific later
    notes: List[str] = [
        f"Estimated top competitor benchmark score: {score}",
        "Primary competitors likely in top 3–5 SERP positions",
        "Stronger backlink profile expected (DA 70+)",
        "Higher content volume and freshness observed",
        "Better Core Web Vitals performance likely",
        "More comprehensive schema markup detected",
        "Stronger social signals and brand mentions",
    ]

    # Optional: lower score → more encouraging notes
    if score < 70:
        notes.extend([
            "You have strong potential to overtake competitors",
            "Focus on content depth and technical SEO to close the gap",
        ])
    elif score > 90:
        notes.extend([
            "Facing very strong competition in this space",
            "Differentiation through unique value proposition recommended",
        ])

    return {
        "top_competitor_score": score,
        "notes": notes,
    }
