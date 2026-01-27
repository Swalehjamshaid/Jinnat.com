import logging
from bs4 import BeautifulSoup

logger = logging.getLogger("audit_engine")

async def analyze_onpage(pages: list):
    """Advanced on-page SEO scoring for a list of pages."""
    if not pages:
        return {"score": 0, "issues": []}

    total_score = 0
    issues = []

    for page in pages:
        url = page.get("url")
        html = page.get("html", "")
        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")
        page_score = 100

        # Title tag
        if not soup.find("title"):
            page_score -= 20
            issues.append(f"Missing title tag on {url}")

        # Meta description
        if not soup.find("meta", attrs={"name": "description"}):
            page_score -= 20
            issues.append(f"Missing meta description on {url}")

        # H1 tag
        h1_tags = soup.find_all("h1")
        if len(h1_tags) != 1:
            page_score -= 10
            issues.append(f"H1 issue on {url} ({len(h1_tags)} found)")

        # Images alt
        images = soup.find_all("img")
        if images:
            images_without_alt = [img for img in images if not img.get("alt")]
            page_score -= 5 * len(images_without_alt)
            if images_without_alt:
                issues.append(f"{len(images_without_alt)} images missing alt on {url}")

        total_score += max(page_score, 0)

    avg_score = total_score / len(pages)
    return {"score": avg_score, "issues": issues[:15]}  # top 15 issues
