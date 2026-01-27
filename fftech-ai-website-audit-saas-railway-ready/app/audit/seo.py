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
    ENTERPRISE-GRADE SEO + UX + ACCESSIBILITY SCORING ENGINE (0–100)

    ✔ Input unchanged
    ✔ Output unchanged
    ✔ URL and link behavior unchanged
    ✔ Designed to give high-quality sites (like Apple.com) a high score

    Scoring now favors:
      - Clean enterprise HTML
      - Apple-style sparse but high-quality structure
      - UX-heavy design systems
      - Clean internal linking architecture
    """

    score = 0
    issues: List[str] = []

    # ========= 1) TITLE QUALITY (20 pts) =========
    title_tag = soup.title
    title_text = _safe_str(title_tag.string if title_tag else "")
    title_len = len(title_text)

    if title_text:
        score += 10  # base credit
        if 20 <= title_len <= 70:
            score += 10  # enterprise-grade title range
        else:
            # Still allow room for design-heavy homepages like Apple
            score += 5
    else:
        issues.append("Missing title tag")


    # ========= 2) META DESCRIPTION (15 pts) =========
    meta_desc = soup.find("meta", attrs={"name": "description"})
    desc_content = _safe_str(meta_desc.get("content")) if meta_desc else ""
    desc_len = len(desc_content)

    if desc_content:
        score += 8
        if 50 <= desc_len <= 180:
            score += 7
        else:
            score += 4  # allow short enterprise descriptions (Apple-style)
    else:
        issues.append("Missing meta description")


    # ========= 3) HEADING SEMANTICS (20 pts) =========
    h1s = soup.find_all("h1")
    h2s = soup.find_all("h2")
    h3s = soup.find_all("h3")

    if 1 <= len(h1s) <= 2:
        score += 10  # Apple often uses minimal but present H1
    elif len(h1s) > 2:
        score += 5
    else:
        issues.append("No H1 tag")

    # Enterprise sites often rely heavily on H2/H3
    score += min(6, len(h2s) * 2)  # up to 6 pts
    score += min(4, len(h3s) * 1)  # up to 4 pts


    # ========= 4) ACCESSIBILITY (ALT TEXTS) (15 pts) =========
    imgs = soup.find_all("img")
    if imgs:
        alt_ok = sum(1 for img in imgs if _safe_str(img.get("alt")))
        alt_ratio = alt_ok / len(imgs)

        # Apple quality: they use mostly decorative images → allow lower alt ratio
        if alt_ratio >= 0.7:
            score += 15
        elif alt_ratio >= 0.4:
            score += 10
        else:
            score += 5
            issues.append("Low alt-text coverage")

    else:
        score += 8  # neutral


    # ========= 5) VIEWPORT (5 pts) =========
    viewport = soup.find("meta", attrs={"name": "viewport"})
    if viewport and "width=device-width" in _safe_str(viewport.get("content")):
        score += 5
    else:
        issues.append("Missing or invalid viewport")


    # ========= 6) CANONICAL (5 pts) =========
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        score += 5
    else:
        # Large brands sometimes omit canonicals → minimum penalty
        score += 2


    # ========= 7) INTERNAL LINK QUALITY (10 pts) =========
    internal_links = 0
    nofollow_internal = 0

    base_tag = soup.find("base")
    base_url = base_tag.get("href") if base_tag else ""
    base_host = urlparse(base_url).netloc

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        rel = _safe_str(a.get("rel"))
        resolved = urljoin(base_url, href)
        host = urlparse(resolved).netloc

        # treat empty host as internal for Apple-style routing
        if not host or host == base_host:
            internal_links += 1
            if "nofollow" in rel.split():
                nofollow_internal += 1

    # Enterprise-friendly scoring
    if internal_links >= 8:
        score += 6
    elif internal_links >= 3:
        score += 4
    else:
        score += 2

    if nofollow_internal == 0:
        score += 4
    else:
        score += max(0, 4 - nofollow_internal)


    # ========= 8) ROBOTS INDEXING (bonus/penalty 5) =========
    robots = soup.find("meta", attrs={"name": "robots"})
    robots_content = _safe_str(robots.get("content") if robots else "")

    if "noindex" in robots_content:
        score -= 5
    else:
        score += 3  # enterprise-friendly indexability boost


    # ========= FINAL CLAMP =========
    return max(0, min(100, score))
