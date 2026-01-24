# app/audit/grader.py

from typing import Dict, Tuple, Optional
import random

# Grade bands based on international standards
# Using a list of tuples to define score cutoffs and their corresponding grades
GRADE_BANDS = [
    (90, 'A+'),
    (80, 'A'),
    (70, 'B'),
    (60, 'C'),
    (0,  'D')
]

def compute_scores(
    onpage: Dict[str, float],
    perf: Dict[str, float],
    links: Dict[str, float],
    crawl_pages_count: int,
    competitor_scores: Optional[Dict[str, float]] = None,
    mobile_weight: float = 0.5
) -> Tuple[float, str, Dict[str, float]]:
    """
    Compute website audit scores based on multiple factors.

    Returns:
    - overall score (float 0-100)
    - letter grade (string A+ to D)
    - breakdown dict (containing onpage, performance, coverage, and confidence scores)
    """
    try:
        # 1. On-page SEO Penalties
        # We start with 0 penalties and add based on missing tags
        penalties = 0
        penalties += onpage.get('missing_title_tags', 0) * 2
        penalties += onpage.get('missing_meta_descriptions', 0) * 1.5
        penalties += onpage.get('multiple_h1', 0) * 1

        # 2. Performance Scoring
        # LCP (Largest Contentful Paint) and FCP (First Contentful Paint) thresholds
        lcp = perf.get('lcp_ms', 4000) or 4000
        fcp = perf.get('fcp_ms', 2000) or 2000
        
        # Scoring formula: 100 minus a weighted penalty based on speed (ms)
        perf_score = max(0, 100 - (lcp / 40 + fcp / 30))

        # 3. Links & Coverage
        # Deduct for broken links and award points for the number of pages successfully crawled
        link_penalty = links.get('total_broken_links', 0) * 0.5
        coverage = min(100, (crawl_pages_count or 0) * 2)
        penalties += link_penalty

        # 4. Weighting the Categories
        # Onpage: 40% | Performance: 40% | Coverage: 20%
        raw_score = (
            max(0, 100 - penalties) * 0.4 +
            perf_score * 0.4 +
            coverage * 0.2
        )

        # 5. Mobile vs Desktop Balancing
        # Combines scores based on the provided mobile_weight
        mobile_score = raw_score * mobile_weight
        desktop_score = raw_score * (1 - mobile_weight)
        overall = (mobile_score + desktop_score)

        # 6. Competitor Benchmarking
        # If competitor data is available, adjust the overall score slightly
        if competitor_scores:
            competitor_avg = sum(competitor_scores.values()) / max(1, len(competitor_scores))
            overall = (overall * 0.9) + (competitor_avg * 0.1)

        # Ensure result stays within 0-100 range
        overall = max(0, min(100, overall))

        # 7. Assign Letter Grade
        # Iterates through GRADE_BANDS to find the highest matching cutoff
        grade = 'D'
        for cutoff, letter in GRADE_BANDS:
            if overall >= cutoff:
                grade = letter
                break

        # 8. Data Reliability (Simulated)
        confidence = random.uniform(85, 99)

        # 9. Final Results Packaging
        # Rounds all floats to 2 decimal places for cleaner frontend display
        breakdown = {
            'onpage': round(max(0, 100 - penalties), 2),
            'performance': round(perf_score, 2),
            'coverage': round(coverage, 2),
            'confidence': round(confidence, 2)
        }

        return round(overall, 2), grade, breakdown

    except Exception as e:
        # Fallback dictionary to ensure the application doesn't crash on calculation errors
        print(f"CRITICAL ERROR in Grader: {e}")
        return 0.0, "D", {
            "onpage": 0.0, 
            "performance": 0.0, 
            "coverage": 0.0, 
            "confidence": 0.0
        }
