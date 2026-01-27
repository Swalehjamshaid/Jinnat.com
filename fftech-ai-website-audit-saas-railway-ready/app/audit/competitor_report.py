# app/audit/competitor_report.py

"""
Enhanced Competitor Analysis Engine (Lightweight & Deterministic)

⚡ This module provides a more realistic competitor scoring algorithm while
   preserving the EXACT input/output structure required by the existing system.

🔒 No external HTTP calls are made — safe for Railway and offline environments.

🎯 Input:  get_top_competitor_score(url: str)
🎯 Output: integer between 70–95 (same range as before for UI compatibility)

The algorithm simulates:
- Market authority
- Website age category
- Industry competitiveness
- Content depth signals
- Brand trust factors
- Technical confidence score
"""

import hashlib
import math

def get_top_competitor_score(url: str) -> int:
    """
    Generate a realistic competitor score using deterministic heuristics
    while matching the original return signature.

    The score range remains 70–95 for UI compatibility.
    """

    # Normalize URL
    clean_url = url.lower().strip()

    # --- 1) Deterministic seed using SHA1 (stable across runs)
    seed = int(hashlib.sha1(clean_url.encode()).hexdigest(), 16)

    # --- 2) Domain age signal (simulated using domain length)
    # Shorter domains often correlate with stronger SEO history.
    domain_length = len(clean_url.split("//")[-1].split("/")[0])
    domain_age_score = max(0, 30 - domain_length)  # shorter = higher authority
    domain_age_score = max(5, min(domain_age_score, 20))  # clamp 5–20

    # --- 3) Industry competitiveness signal
    # Use keyword matching to simulate competitive niches
    industry_keywords = {
        "tech": 18,
        "ai": 20,
        "shop": 15,
        "store": 15,
        "news": 17,
        "blog": 10,
        "agency": 14,
        "finance": 20,
        "crypto": 12,
        "health": 18,
        "travel": 16,
    }

    industry_score = 10
    for word, value in industry_keywords.items():
        if word in clean_url:
            industry_score += value
            break

    industry_score = min(industry_score, 25)

    # --- 4) Brand authority estimation (simulated)
    # Hash-based pseudo-random but deterministic
    brand_raw = (seed % 1000) / 1000
    brand_score = 10 + (brand_raw * 10)  # range 10–20

    # --- 5) Content depth simulation
    # Use domain vowel count as a proxy for human-friendly naming style
    vowels = sum(1 for c in clean_url if c in "aeiou")
    content_score = min(20, 8 + vowels)

    # --- 6) Technical reliability heuristic
    technical_score = 15 + ((seed >> 8) % 10)  # 15–25

    # Weighted scoring model
    weighted = (
        (domain_age_score * 0.20)
        + (industry_score * 0.20)
        + (brand_score * 0.25)
        + (content_score * 0.15)
        + (technical_score * 0.20)
    )

    # Scale result to fit your existing UI range (70–95)
    final_score = 70 + (weighted % 26)  # ensures output 70–95
    return int(final_score)
