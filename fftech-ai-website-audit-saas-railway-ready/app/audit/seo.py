# app/audit/seo.py
from bs4 import BeautifulSoup

def calculate_seo_score(soup: BeautifulSoup) -> int:
    """
    SEO scoring based on:
    - Title tag (20 points)
    - Meta description (20 points)
    - H1 tags (20 points)
    - Image alt attributes (20 points)
    - Penalize too many nofollow links (-10 max)
    """
    score = 0

    # Title tag
    if soup.title and soup.title.string:
        score += 20

    # Meta description
    meta = soup.find("meta", {"name": "description"})
    if meta and meta.get("content"):
        score += 20

    # H1 tags
    h1_tags = soup.find_all("h1")
    if h1_tags:
        score += 20

    # Images with alt
    images = soup.find_all("img")
    images_with_alt = [img for img in images if img.get("alt")]
    if images:
        score += int(20 * len(images_with_alt) / len(images))

    # Penalize nofollow links
    nofollow_links = soup.find_all("a", rel="nofollow")
    score -= min(len(nofollow_links) * 2, 10)

    return max(0, min(score, 100))
