from typing import Tuple, Optional, Dict
from dataclasses import dataclass
from enum import Enum


class GradeLevel(Enum):
    """Standardized grade levels with clear thresholds and descriptions."""
    A_PLUS = ("A+", 90, 100, "Outstanding – world-class performance")
    A     = ("A",  80, 89,  "Excellent – very strong position")
    B     = ("B",  70, 79,  "Good – competitive but room to improve")
    C     = ("C",  60, 69,  "Average – needs noticeable optimization")
    D     = ("D",  0,  59,  "Below average – significant improvements required")


@dataclass
class AuditGrade:
    """
    Rich grade object – keeps simple tuple output compatible while allowing
    future UI/debug/report extensions without breaking existing code.
    """
    overall_score: int
    grade: str
    grade_level: GradeLevel
    explanation: str
    breakdown: Dict[str, int]  # for future detailed reporting


def compute_grade(
    seo: int,
    performance: int,
    competitor: int,
    weights: Optional[Dict[str, float]] = None,
    min_score: int = 0,
    max_score: int = 100
) -> Tuple[int, str]:
    """
    Compute overall audit score and grade according to best practices.

    Preserves exact same input/output signature as before.

    Args:
        seo: SEO score (0–100)
        performance: Performance score (0–100)
        competitor: Competitor benchmark score (0–100)
        weights: Optional custom weights (default: SEO 40%, Performance 35%, Competitor 25%)
        min_score / max_score: clamp range (usually 0–100)

    Returns:
        Tuple[int, str] → (overall_score, grade_letter)
        e.g. (87, "A")
    """
    # Default weights – balanced modern SEO/performance priority
    if weights is None:
        weights = {
            "seo": 0.40,
            "performance": 0.35,
            "competitor": 0.25
        }

    # Validate inputs
    for name, value in [("seo", seo), ("performance", performance), ("competitor", competitor)]:
        if not isinstance(value, (int, float)) or not (min_score <= value <= max_score):
            raise ValueError(f"Invalid {name} score: {value} (must be {min_score}–{max_score})")

    # Weighted average
    overall = int(
        seo * weights["seo"] +
        performance * weights["performance"] +
        competitor * weights["competitor"]
    )

    # Clamp final score
    overall = max(min_score, min(max_score, overall))

    # Determine grade level
    for level in sorted(GradeLevel, key=lambda g: g.value[1], reverse=True):
        if overall >= level.value[1]:
            grade_letter = level.value[0]
            break
    else:
        grade_letter = GradeLevel.D.value[0]

    return overall, grade_letter


# ────────────────────────────────────────────────
# Optional richer version (for future use without breaking old code)
# ────────────────────────────────────────────────

def compute_grade_detailed(
    seo: int,
    performance: int,
    competitor: int,
    weights: Optional[Dict[str, float]] = None
) -> AuditGrade:
    """
    Extended version that returns rich object – safe to use in new code.
    Keeps backward compatibility by providing .overall_score and .grade
    """
    overall, grade_letter = compute_grade(seo, performance, competitor, weights)

    # Find matching enum for description
    grade_enum = next(
        (g for g in GradeLevel if g.value[0] == grade_letter),
        GradeLevel.D
    )

    return AuditGrade(
        overall_score=overall,
        grade=grade_letter,
        grade_level=grade_enum,
        explanation=grade_enum.value[3],
        breakdown={
            "seo": seo,
            "performance": performance,
            "competitor": competitor,
            "weighted_overall": overall
        }
    )
