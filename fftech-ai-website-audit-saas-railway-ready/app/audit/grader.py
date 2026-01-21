from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Weights should sum to 1.0
# Order reflects priority in most SEO audits (on-page and technical usually matter most)
CATEGORY_WEIGHTS: Dict[str, float] = {
    'executive':          0.10,   # AI summary quality / executive perception
    'overall':            0.10,   # General health
    'crawlability':       0.20,   # Critical foundation
    'onpage':             0.25,   # Highest weight – content/SEO signals
    'performance':        0.20,   # Core Web Vitals + speed
    'mobile_security_intl': 0.10, # Mobile + HTTPS + international
    'competitor_gap':     0.03,   # Relative position
    'broken_links':       0.02,   # High-impact issue
    'opportunities':      0.00,   # More aspirational – low direct scoring weight
}

# Verify weights sum to ~1.0 (allow small float error)
WEIGHT_SUM = sum(CATEGORY_WEIGHTS.values())
if abs(WEIGHT_SUM - 1.0) > 0.001:
    logger.warning(f"Category weights sum to {WEIGHT_SUM:.4f} instead of 1.0")


def to_grade(score: float) -> str:
    """
    Convert numeric score (0–100) to academic-style grade.
    Very strict scale — only near-perfect sites get A+.
    """
    score = max(0.0, min(100.0, score))  # clamp to valid range

    if score >= 97:   return 'A+'
    if score >= 93:   return 'A'
    if score >= 90:   return 'A-'
    if score >= 87:   return 'B+'
    if score >= 83:   return 'B'
    if score >= 80:   return 'B-'
    if score >= 77:   return 'C+'
    if score >= 73:   return 'C'
    if score >= 70:   return 'C-'
    if score >= 60:   return 'D'
    return 'F'  # Changed from 'D' to 'F' for scores <60 (more honest)


def overall_score(category_scores: Dict[str, float]) -> float:
    """
    Calculate weighted overall score from category scores.
    
    Returns:
        float: Rounded score between 0 and 100
    """
    if not category_scores:
        logger.warning("No category scores provided → returning 0")
        return 0.0

    total = 0.0
    used_weights = 0.0

    for category, weight in CATEGORY_WEIGHTS.items():
        value = category_scores.get(category, 0.0)
        # Clamp individual category scores to 0–100
        value = max(0.0, min(100.0, value))
        total += value * weight
        used_weights += weight

    # If some categories are missing, normalize to prevent deflation
    if used_weights > 0 and used_weights < 1.0:
        total = total * (1.0 / used_weights)

    final_score = round(total, 2)
    return final_score


def grade_with_label(score: float) -> tuple[str, str]:
    """
    Returns (grade, descriptive_label) for use in reports/UI.
    """
    grade = to_grade(score)
    labels = {
        'A+': 'Excellent – Industry-leading performance',
        'A':  'Very Good – Strong SEO foundation',
        'A-': 'Good – Minor improvements needed',
        'B+': 'Above Average – Solid but optimizable',
        'B':  'Average – Several areas need work',
        'B-': 'Below Average – Important fixes required',
        'C+': 'Fair – Significant SEO issues',
        'C':  'Poor – Major optimization needed',
        'C-': 'Very Poor – Serious problems detected',
        'D':  'Critical – High risk of poor rankings',
        'F':  'Failing – Immediate action required'
    }
    return grade, labels.get(grade, 'Unknown')


# Optional: debug helper
def explain_score(category_scores: Dict[str, float]) -> str:
    """Returns a human-readable explanation of how the score was calculated."""
    lines = ["Score calculation:"]
    total_contrib = 0.0
    for cat, w in CATEGORY_WEIGHTS.items():
        val = category_scores.get(cat, 0.0)
        contrib = round(val * w, 2)
        total_contrib += contrib
        lines.append(f"  • {cat:22} {val:5.1f}% × {w:4.2f} = {contrib:5.2f}%")
    lines.append(f"  Final weighted score: {total_contrib:.2f}")
    return "\n".join(lines)
