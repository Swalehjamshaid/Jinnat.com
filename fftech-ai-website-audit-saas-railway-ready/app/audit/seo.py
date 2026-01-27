from typing import Dict, Any
from bs4 import BeautifulSoup


def summarize_basic_seo(html: str) -> Dict[str, Any]:
    """
    Extracts basic but more meaningful SEO signals:
    - Title presence and length
    - H1 presence and count
    - Meta description presence and length
    - Viewport meta (mobile-friendliness)
    - Canonical link presence
    - Open Graph / Twitter meta tags presence
    Returns the same output structure as before, but with a better score calculation.
    """
    soup = BeautifulSoup(html or "", "html.parser")

    # Title
    title_tag = soup.title
    title = title_tag.string.strip() if title_tag and title_tag.string else ""
    title_length = len(title)
    has_title = 1 if title else 0
    title_good = 1 if 10 <= title_length <= 70 else 0  # Google prefers 50-60 chars

    # H1 tags
    h1_tags = soup.find_all("h1")
    h1_count = len(h1_tags)
    has_h1 = 1 if h1_count > 0 else 0
    h1_good = 1 if 1 <= h1_count <= 2 else 0  # usually 1 ideal, 2 acceptable

    # Meta description
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc_tag["content"].strip() if meta_desc_tag and meta_desc_tag.get("content") else ""
    meta_desc_ok = bool(meta_desc)
    meta_desc_length = len(meta_desc)
    meta_desc_good = 1 if 50 <= meta_desc_length <= 160 else 0  # ideal range

    # Viewport meta (mobile friendliness)
    viewport_tag = soup.find("meta", attrs={"name": "viewport"})
    has_viewport = 1 if viewport_tag else 0

    # Canonical link
    canonical_tag = soup.find("link", rel="canonical")
    has_canonical = 1 if canonical_tag and canonical_tag.get("href") else 0

    # Basic social meta (Open Graph / Twitter)
    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")
    twitter_card = soup.find("meta", attrs={"name": "twitter:card"})
    has_social_meta = 1 if og_title or og_desc or twitter_card else 0

    # Improved scoring (0–100)
    # Weights are balanced for modern SEO priorities
    seo_score = (
        has_title       * 15 +
        title_good      * 10 +
        has_h1          * 10 +
        h1_good         * 10 +
        meta_desc_ok    * 15 +
        meta_desc_good  * 15 +
        has_viewport    * 10 +
        has_canonical   * 8  +
        has_social_meta * 7
    )

    # Cap at 100
    seo_score = min(100, seo_score)

    return {
        "title": title,
        "title_length": title_length,
        "h1_count": h1_count,
        "has_meta_description": meta_desc_ok,
        "meta_description_length": meta_desc_length,
        "has_viewport": bool(has_viewport),
        "has_canonical": bool(has_canonical),
        "has_social_meta": bool(has_social_meta),
        "seo_score": seo_score,
        # Optional: detailed breakdown for future UI use
        "details": {
            "title_status": "good" if title_good else "missing or too long/short",
            "h1_status": "good" if h1_good else "missing or too many",
            "meta_desc_status": "good" if meta_desc_good else "missing or too long/short",
            "viewport_status": "present" if has_viewport else "missing",
            "canonical_status": "present" if has_canonical else "missing"
        }
    }
