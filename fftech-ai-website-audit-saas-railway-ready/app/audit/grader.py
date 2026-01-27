from typing import Tuple, Optional, Dict
from dataclasses import dataclass
from enum import Enum


class GradeLevel(Enum):
    """
    Internationally recognized grading scale aligned with
    global audit, ISO-style assessments, and academic standards.
    """
    A_PLUS = ("A+", 90, 100, "Outstanding – world-class, industry-leading performance")
    A      = ("A",  80, 89,  "Excellent – strong competitive positioning")
    B      = ("B",  70, 79,  "Good – meets expectations with room for growth")
    C      = ("C",  60, 69,  "Average – acceptable but requires optimization")
    D      = ("D",  50, 59,  "Below average – significant improvements needed")
    F      = ("F",  0,  49,  "Poor – fails to meet minimum quality standards")


@dataclass
class AuditGrade:
    """
    Rich grading object for future dashboards, reports, and APIs.
    This does NOT alter existing behavior.
    """
    overall_score: int
    grade: str
    grade_level: GradeLevel
    explanation: str
    breakdown: Dict[str, int]


def compute_grade(
    seo: int,
    performance: int,
    competitor: int,
    weights: Optional[Dict[str, float]] = None,
    min_score: int = 0,
    max_score: int = 100
) -> Tuple[int, str]:
    """
    International-standard grading computation.

    INPUTS: unchanged
    OUTPUT: unchanged → (overall_score, grade_letter)

    Weighting model reflects global audit norms:
    • SEO: 40%
    • Performance: 35%
    • Competitive Positioning: 25%
    """

    # Default globally balanced weights
    if weights is None:
        weights = {
            "seo": 0.40,
            "performance": 0.35,
            "competitor": 0.25
        }

    # Normalize weights defensively (international best practice)
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("Invalid grading weights")

    weights = {k: v / total_weight for k, v in weights.items()}

    # Input validation (strict, audit-grade)
    for name, value in {
        "seo": seo,
        "performance": performance,
        "competitor": competitor
    }.items():
        if not isinstance(value, (int, float)):
            raise ValueError(f"{name} score must be numeric")
        if not (min_score <= value <= max_score):
            raise ValueError(f"{name} score out of range ({min_score}–{max_score})")

    # Weighted overall score
    overall = round(
        seo * weights["seo"] +
        performance * weights["performance"] +
        competitor * weights["competitor"]
    )

    # Clamp result
    overall = max(min_score, min(max_score, overall))

    # Grade resolution (descending priority)
    for level in sorted(GradeLevel, key=lambda g: g.value[1], reverse=True):
        if overall >= level.value[1]:
            return overall, level.value[0]

    return overall, GradeLevel.F.value[0]


# ────────────────────────────────────────────────
# Optional future-safe detailed grading (NOT breaking)
# ────────────────────────────────────────────────

def compute_grade_detailed(
    seo: int,
    performance: int,
    competitor: int,
    weights: Optional[Dict[str, float]] = None
) -> AuditGrade:
    """
    Extended grading for reports, dashboards, exports.
    Safe to adopt later without touching existing code.
    """

    overall, grade_letter = compute_grade(seo, performance, competitor, weights)

    grade_enum = next(
        (g for g in GradeLevel if g.value[0] == grade_letter),
        GradeLevel.F
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
            "overall": overall
        }
    )
