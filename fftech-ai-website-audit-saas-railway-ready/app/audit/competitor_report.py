# app/audit/competitor_report.py
from typing import Dict, List

def top_competitor_score(domain: str) -> int:
    """
    Placeholder: return a stable, demonstrative score.
    Replace with real logic (SERP checks, lighthouse comparisons, etc.).
    """
    # You can seed by domain for repeatable pseudo-scores if desired.
    return 75


def competitor_summary(domain: str) -> Dict[str, int | List[str]]:
    """
    Example structure your UI could use if you later add competitor panels.
    """
    score = top_competitor_score(domain)
    return {
        "top_competitor_score": score,
        "notes": [
            "Ranking overlap TBD",
            "Backlink growth TBD",
            "Content depth TBD",
        ],
    }
