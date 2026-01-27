from typing import Dict, List
from bs4 import BeautifulSoup, Tag
from urllib.parse import urlparse


def calculate_seo_score(soup: BeautifulSoup) -> int:
    """
    Modern, realistic SEO scoring (0–100) based on key on-page signals.

    Scoring breakdown (total 100 points):
    • Title tag presence & quality (25)
    • Meta description presence & quality (20)
    • Heading structure (H1 + H2/H3 usage) (15)
    • Image alt attributes (15)
    • Viewport meta (mobile friendliness) (10)
    • Canonical tag presence (5)
    • Robots meta & noindex check (-10 penalty if noindex)
    • Excessive nofollow internal links penalty (-10 max)

    Designed to be fast, extensible, and aligned with 2025–2026 SEO best practices.
    """
    score = 0
    issues: List[str] = []  # for future logging/debug

    # ────────────────────────────────────────────────
    # 1. Title tag (max 25 points)
    # ────────────────────────────────────────────────
    title_tag = soup.title
    title_text = title_tag.string.strip() if title_tag and title_tag.string else ""
    title_len = len(title_text)

    if title_text:
        score += 15  # base points for existence
        if 10 <= title_len <= 70:
            score += 10  # good length (Google sweet spot ~55–65)
        else:
            issues.append(f"Title length {title_len} chars (ideal: 50–70)")
    else:
        issues.append("Missing <title> tag")

    # ────────────────────────────────────────────────
    # 2. Meta description (max 20 points)
    # ────────────────────────────────────────────────
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc_tag["content"].strip() if meta_desc_tag and meta_desc_tag.get("content") else ""
    meta_len = len(meta_desc)

    if meta_desc:
        score += 10  # existence
        if 50 <= meta_len <= 160:
            score += 10  # good length
        else:
            issues.append(f"Meta description length {meta_len} chars (ideal: 120–155)")
    else:
        issues.append("Missing meta description")

    # ────────────────────────────────────────────────
    # 3. Heading structure (max 15 points)
    # ────────────────────────────────────────────────
    h1_count = len(soup.find_all("h1"))
    h2_h3_count = len(soup.find_all(["h2", "h3"]))

    if h1_count == 1:
        score += 10
    elif h1_count == 0:
        issues.append("No <h1> tag found")
    else:
        issues.append(f"Multiple H1 tags ({h1_count}) – prefer only one")
        score += 5  # partial credit

    if h2_h3_count >= 2:
        score += 5  # good subheading structure

    # ────────────────────────────────────────────────
    # 4. Image alt attributes (max 15 points)
    # ────────────────────────────────────────────────
    images = soup.find_all("img")
    if images:
        with_alt = sum(1 for img in images if img.get("alt") and img["alt"].strip())
        alt_ratio = with_alt / len(images)
        score += int(15 * alt_ratio)
        if with_alt < len(images):
            issues.append(f"{len(images) - with_alt} images missing or empty alt text")
    else:
        score += 5  # no images → no penalty

    # ────────────────────────────────────────────────
    # 5. Mobile friendliness – Viewport meta (10 points)
    # ────────────────────────────────────────────────
    viewport = soup.find("meta", attrs={"name": "viewport"})
    if viewport and "width=device-width" in viewport.get("content", ""):
        score += 10
    else:
        issues.append("Missing or invalid viewport meta tag")

    # ────────────────────────────────────────────────
    # 6. Canonical tag (5 points)
    # ────────────────────────────────────────────────
    if soup.find("link", rel="canonical"):
        score += 5
    else:
        issues.append("Missing rel=canonical")

    # ────────────────────────────────────────────────
    # 7. Robots meta – penalize noindex (-10)
    # ────────────────────────────────────────────────
    robots_meta = soup.find("meta", attrs={"name": "robots"})
    if robots_meta:
        content = robots_meta.get("content", "").lower()
        if "noindex" in content:
            score -= 10
            issues.append("Page has noindex directive")

    # ────────────────────────────────────────────────
    # 8. Penalize excessive nofollow internal links (-10 max)
    # ────────────────────────────────────────────────
    nofollow_count = 0
    base_domain = urlparse(soup.find("base")["href"] if soup.find("base") else "").netloc or ""

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        rel = (a.get("rel") or "").lower()
        if "nofollow" in rel.split():
            parsed_href = urlparse(urljoin(soup.find("base")["href"] if soup.find("base") else "", href))
            if parsed_href.netloc == base_domain or not parsed_href.netloc:
                nofollow_count += 1

    nofollow_penalty = min(nofollow_count * 2, 10)
    score -= nofollow_penalty
    if nofollow_penalty > 0:
        issues.append(f"Excessive internal nofollow links ({nofollow_count})")

    # Final clamp
    final_score = max(0, min(100, score))

    # Optional: return more debug info (you can strip this later)
    return final_score
