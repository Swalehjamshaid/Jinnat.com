# app/audit/grader.py
def compute_grade(seo: int, performance: int, competitor: int):
    """
    Compute overall score and assign a grade
    """
    overall = int((seo + performance + competitor) / 3)

    if overall >= 90:
        grade = "A+"
    elif overall >= 80:
        grade = "A"
    elif overall >= 70:
        grade = "B"
    elif overall >= 60:
        grade = "C"
    else:
        grade = "D"

    return overall, grade
