from typing import List
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

def _safe_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(v) for v in value).strip().lower()
    return str(value).strip().lower()


def calculate_seo_score(soup: BeautifulSoup) -> int:
    """
    WORLD‑CLASS ENTERPRISE SEO SCORING ENGINE (0–100)
    Fully aligned with modern Web Quality Standards:
        - Technical SEO
        - HTML semantics
        - Accessibility
        - Content quality heuristics
        - Internal architecture health
        
    NOTE: Input/Output unchanged.
    """

    score = 0
    issues: List[str] = []

    # ============= 1) TITLE QUALITY (20 pts) =============
    title_tag = soup.title
    title_text = _safe_str(title_tag.string if title_tag else "")
    title_len = len(title_text)

    if title_text:
        score += 10  # basic presence
        if 30 <= title_len <= 60:
            score += 10  # high‑quality title range
        else:
            issues.append("Suboptimal title length")
    else:
        issues.append("Missing title tag")

    # ============= 2) META DESCRIPTION (15 pts) =============
    meta_desc = soup.find("meta", attrs={"name": "description"})
    desc_content = _safe_str(meta_desc.get("content")) if meta_desc else ""
    desc_len = len(desc_content)

    if desc_content:
        score += 8
        if 70 <= desc_len <= 160:
            score += 7
        else:
            issues.append("Poor meta description length")
    else:
        issues.append("Missing meta description")

    # ============= 3) HEADING SEMANTICS (20 pts) =============
    h1s = soup.find_all("h1")
    h2s = soup.find_all("h2")
    h3s = soup.find_all("h3")

    if len(h1s) == 1:
        score += 10
    elif len(h1s) > 1:
        score += 5
        issues.append("Multiple H1 tags")
    else:
        issues.append("No H1 tag")

    # good semantic hierarchy (Apple has excellent structure)
    if len(h2s) >= 2:
        score += 6
    if len(h3s) >= 3:
        score += 4

    # ============= 4) ACCESSIBILITY — ALT ATTRIBUTES (15 pts) =============
    imgs = soup.find_all("img")
    if imgs:
        alt_ok = sum(1 for img in imgs if _safe_str(img.get("alt")))
        alt_ratio = alt_ok / len(imgs)
        score += int(15 * alt_ratio)
        if alt_ratio < 1.0:
            issues.append("Missing alt attributes")
    else:
        score += 5  # no images = neutral

    # ============= 5) VIEWPORT (5 pts) =============
    viewport = soup.find("meta", attrs={"name": "viewport"})
    if viewport and "width=device-width" in _safe_str(viewport.get("content")):
        score += 5
    else:
        issues.append("Viewport missing or invalid")

    # ============= 6) CANONICAL TAG (5 pts) =============
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        score += 5
    else:
        issues.append("Missing canonical URL")

    # ============= 7) INTERNAL LINK QUALITY (10 pts) =============
    internal_links = 0
    broken_links = 0
    nofollow_internal = 0

    base_tag = soup.find("base")
    base_url = base_tag.get("href") if base_tag else ""
    base_host = urlparse(base_url).netloc

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        rel = _safe_str(a.get("rel"))

        resolved = urljoin(base_url, href)
        host = urlparse(resolved).netloc

        if not host or host == base_host:
            internal_links += 1

            # penalize internal nofollow usage
            if "nofollow" in rel.split():
                nofollow_internal += 1

    # strong architecture sites (like Apple) use clean followable internal links
    if internal_links > 10:
        score += 5
    if nofollow_internal == 0:
        score += 5
    else:
        score -= min(5, nofollow_internal)

    # ============= 8) ROBOTS INDEXING (bonus/penalty 5) =============
    robots = soup.find("meta", attrs={"name": "robots"})
    robots_content = _safe_str(robots.get("content") if robots else "")
    if "noindex" in robots_content:
        score -= 5
    else:
        score += 2  # indexable pages tend to be better quality

    # ============= FINAL CLAMP =============
    return max(0, min(100, score))
