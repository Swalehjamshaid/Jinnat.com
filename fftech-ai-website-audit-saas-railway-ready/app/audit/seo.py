import logging
from bs4 import BeautifulSoup

logger = logging.getLogger("audit_engine")

async def analyze_onpage(pages: list):
    """
    FIXED: Now accepts a LIST of dictionaries instead of a DICT.
    """
    if not pages:
        return {"score": 0, "issues": []}

    total_score = 0
    issues = []

    # Iterating through the list of results from crawler.py
    for page in pages:
        url = page.get("url")
        html = page.get("html", "")
        
        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")
        page_score = 100
        
        # Simple SEO Heuristics
        if not soup.find("title"):
            page_score -= 20
            issues.append(f"Missing title tag on {url}")
            
        if not soup.find("meta", attrs={"name": "description"}):
            page_score -= 20
            issues.append(f"Missing meta description on {url}")

        total_score += max(page_score, 0)

    avg_score = total_score / len(pages)
    
    return {
        "score": avg_score,
        "issues": issues[:10] # Return top 10 issues
    }
