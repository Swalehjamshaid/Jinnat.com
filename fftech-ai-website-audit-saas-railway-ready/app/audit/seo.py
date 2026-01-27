# app/audit/seo.py
from bs4 import BeautifulSoup

def calculate_seo_score(soup: BeautifulSoup) -> int:
    """
    Basic SEO scoring based on:
    - Title presence
    - Meta description
    - H1 tags
    - Image alt attributes
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

    # Images with alt text
    images = soup.find_all("img")
    images_with_alt = [img for img in images if img.get("alt")]
    if images:
        score += int(20 * len(images_with_alt) / len(images))

    # Links with rel="nofollow" (penalty)
    nofollow_links = soup.find_all("a", rel="nofollow")
    if nofollow_links:
        score -= min(len(nofollow_links) * 2, 10)

    return max(0, min(score, 100))
