from typing import List
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin


def _safe_str(value) -> str:
    """
    Normalize BeautifulSoup values to a safe, lowercase string.
    Handles None, list, Tag, and str consistently.
    """
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(v) for v in value).strip().lower()
    return str(value).strip().lower()


def calculate_seo_score(soup: BeautifulSoup) -> int:
    """
    International-standard on-page SEO scoring (0–100).

    Conforms to:
    • Google Search Central guidelines
    • Lighthouse SEO heuristics
    • W3C HTML semantics
    • Enterprise audit scoring practices

    INPUT / OUTPUT UNCHANGED
    """
    score = 0
    issues: List[str] = []  # retained for future audit logging

    # ────────────────────────────────────────────────
    # 1. Title tag quality (25)
    # ────────────────────────────────────────────────
    title_tag = soup.title
    title_text = _safe_str(title_tag.string if title_tag else "")
    title_len = len(title_text)

    if title_text:
        score += 15  # presence
        if 30 <= title_len <= 65:
            score += 10  # Google-recommended range
        else:
            issues.append(f"Suboptimal title length ({title_len} chars)")
    else:
        issues.append("Missing <title> tag")

    # ────────────────────────────────────────────────
    # 2. Meta description quality (20)
    # ────────────────────────────────────────────────
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = _safe_str(meta_desc_tag.get("content") if meta_desc_tag else "")
    meta_len = len(meta_desc)

    if meta_desc:
        score += 10  # presence
        if 70 <= meta_len <= 160:
            score += 10
        else:
            issues.append(f"Suboptimal meta description length ({meta_len} chars)")
    else:
        issues.append("Missing meta description")

    # ────────────────────────────────────────────────
    # 3. Heading hierarchy (15)
    # ────────────────────────────────────────────────
    h1_tags = soup.find_all("h1")
    h2_h3_tags = soup.find_all(["h2", "h3"])

    if len(h1_tags) == 1:
        score += 10
    elif len(h1_tags) > 1:
        score += 5
        issues.append(f"Multiple H1 tags ({len(h1_tags)})")
    else:
        issues.append("No H1 tag found")

    if len(h2_h3_tags) >= 2:
        score += 5

    # ────────────────────────────────────────────────
    # 4. Image alt attributes (15)
    # ────────────────────────────────────────────────
    images = soup.find_all("img")
    if images:
        with_alt = sum(1 for img in images if _safe_str(img.get("alt")))
        alt_ratio = with_alt / len(images)
        score += int(15 * alt_ratio)
        if with_alt < len(images):
            issues.append(f"{len(images) - with_alt} images missing alt text")
    else:
        score += 5  # neutral handling (no images ≠ penalty)

    # ────────────────────────────────────────────────
    # 5. Mobile friendliness – viewport (10)
    # ────────────────────────────────────────────────
    viewport = soup.find("meta", attrs={"name": "viewport"})
    viewport_content = _safe_str(viewport.get("content") if viewport else "")

    if "width=device-width" in viewport_content:
        score += 10
    else:
        issues.append("Missing or invalid viewport meta")

    # ────────────────────────────────────────────────
    # 6. Canonicalization (5)
    # ────────────────────────────────────────────────
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        score += 5
    else:
        issues.append("Missing canonical tag")

    # ────────────────────────────────────────────────
    # 7. Robots noindex penalty (-10)
    # ────────────────────────────────────────────────
    robots_meta = soup.find("meta", attrs={"name": "robots"})
    robots_content = _safe_str(robots_meta.get("content") if robots_meta else "")

    if "noindex" in robots_content:
        score -= 10
        issues.append("Page blocked from indexing (noindex)")

    # ────────────────────────────────────────────────
    # 8. Excessive internal nofollow links (-10 max)
    # ────────────────────────────────────────────────
    nofollow_count = 0

    base_tag = soup.find("base")
    base_href = base_tag.get("href") if base_tag else ""
    base_domain = urlparse(base_href).netloc

    for a in soup.find_all("a", href=True):
        href = _safe_str(a.get("href"))
        rel_text = _safe_str(a.get("rel"))

        if "nofollow" in rel_text.split():
            parsed = urlparse(urljoin(base_href, href))
            if not parsed.netloc or parsed.netloc == base_domain:
                nofollow_count += 1

    nofollow_penalty = min(nofollow_count * 2, 10)
    score -= nofollow_penalty

    if nofollow_penalty:
        issues.append(f"Excessive internal nofollow links ({nofollow_count})")

    # ────────────────────────────────────────────────
    # Final ISO-style clamp
    # ────────────────────────────────────────────────
    return max(0, min(100, score))
