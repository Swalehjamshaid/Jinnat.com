# Constants for grading consistency
GRADE_BANDS = [(90, 'A+'), (80, 'A'), (70, 'B'), (60, 'C'), (0, 'D')]

def compute_scores(onpage: dict, perf: dict, links: dict, crawl_pages_count: int):
    """
    Existing logic to calculate detailed audit scores.
    """
    penalties = 0
    penalties += onpage.get('missing_title_tags', 0) * 2
    penalties += onpage.get('missing_meta_descriptions', 0) * 1.5
    penalties += onpage.get('multiple_h1', 0) * 1
    penalties += links.get('total_broken_links', 0) * 0.5
    
    lcp = perf.get('lcp_ms', 4000) or 4000
    fcp = perf.get('fcp_ms', 2000) or 2000
    perf_score = max(0, 100 - (lcp/40 + fcp/30))
    
    coverage = min(100, crawl_pages_count * 2)
    
    raw = max(0, 100 - penalties) * 0.5 + perf_score * 0.3 + coverage * 0.2
    overall = max(0, min(100, raw))
    
    grade = 'D'
    for cutoff, letter in GRADE_BANDS:
        if overall >= cutoff:
            grade = letter
            break
            
    return overall, grade, {
        'onpage': max(0, 100 - penalties), 
        'performance': perf_score, 
        'coverage': coverage
    }

# --- MANDATORY FIX: Function required by crawler.py ---
def to_grade(score: int) -> str:
    """
    Converts a numerical score into a letter grade.
    This fixes the ImportError in app/audit/crawler.py.
    """
    for cutoff, letter in GRADE_BANDS:
        if score >= cutoff:
            return letter
    return "D"
