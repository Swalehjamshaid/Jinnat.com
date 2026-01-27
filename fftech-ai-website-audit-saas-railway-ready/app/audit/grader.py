import re
from typing import Dict, Any
from bs4 import BeautifulSoup
from urllib.parse import urlparse


def grade_website(html: str, url: str) -> Dict[str, Any]:
    """
    Analyzes a single HTML document and computes SEO / Performance / Security / Content scores.
    Returns a nested breakdown suitable for dashboards or reports.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    parsed_url = urlparse(url)
    base_domain = parsed_url.netloc

    breakdown: Dict[str, Any] = {
        "seo": {"score": 0, "issues": [], "details": {}},
        "performance": {"score": 0, "issues": [], "details": {}},
        "security": {"score": 0, "issues": [], "details": {}},
        "content": {"score": 0, "issues": [], "details": {}},
    }

    # ────────────────────────────────────────────────
    # 1) SEO Score (max 100)
    # ────────────────────────────────────────────────
    seo = breakdown["seo"]

    # Title
    title_tag = soup.title
    title = title_tag.string.strip() if title_tag and title_tag.string else ""
    title_len = len(title)
    if title:
        seo["score"] += 20
        seo["details"]["title"] = title
        if 10 <= title_len <= 70:
            seo["score"] += 10
        else:
            seo["issues"].append(f"Title length {title_len} chars (ideal: 50–60)")
    else:
        seo["issues"].append("Missing <title> tag")

    # Meta description
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc_tag["content"].strip() if meta_desc_tag and meta_desc_tag.get("content") else ""
    meta_len = len(meta_desc)
    if meta_desc:
        seo["score"] += 20
        seo["details"]["meta_description"] = meta_desc
        if 50 <= meta_len <= 160:
            seo["score"] += 10
        else:
            seo["issues"].append(f"Meta description length {meta_len} chars (ideal: 120–155)")
    else:
        seo["issues"].append("Missing meta description")

    # Headings structure
    h1_count = len(soup.find_all("h1"))
    if h1_count == 1:
        seo["score"] += 15
    elif h1_count == 0:
        seo["issues"].append("No <h1> tag found")
    else:
        seo["issues"].append(f"Multiple H1 tags ({h1_count}) – prefer only one")

    # Viewport (mobile)
    if soup.find("meta", attrs={"name": "viewport"}):
        seo["score"] += 10
    else:
        seo["issues"].append("Missing viewport meta tag (mobile friendliness)")

    # Canonical
    if soup.find("link", rel="canonical"):
        seo["score"] += 8
    else:
        seo["issues"].append("Missing rel=canonical link")

    seo["score"] = min(100, seo["score"])

    # ────────────────────────────────────────────────
    # 2) Performance Score (max 100) – client-side heuristics
    # ────────────────────────────────────────────────
    perf = breakdown["performance"]

    scripts = soup.find_all("script", src=True)
    styles = soup.find_all("link", rel="stylesheet")
    blocking = soup.find_all(["script", "link"], attrs={"rel": "preload", "as": "script"})  # rough check

    perf["score"] = 100

    if len(scripts) > 15:
        perf["score"] -= 20
        perf["issues"].append(f"High number of JS files ({len(scripts)})")
    if len(styles) > 8:
        perf["score"] -= 15
        perf["issues"].append(f"High number of CSS files ({len(styles)})")

    if not soup.find("meta", attrs={"name": "viewport"}):
        perf["score"] -= 15
        perf["issues"].append("Missing viewport – impacts mobile performance")

    if blocking:
        perf["score"] -= 10
        perf["issues"].append("Potential render-blocking resources detected")

    perf["score"] = max(0, perf["score"])

    # ────────────────────────────────────────────────
    # 3) Security Score (max 100) – mostly header-based, limited by HTML
    # ────────────────────────────────────────────────
    sec = breakdown["security"]

    sec["score"] = 0

    if parsed_url.scheme == "https":
        sec["score"] += 40
    else:
        sec["issues"].append("Not using HTTPS")

    # CSP (limited visibility in HTML)
    if soup.find("meta", attrs={"http-equiv": "Content-Security-Policy"}):
        sec["score"] += 25
    else:
        sec["issues"].append("No Content-Security-Policy visible")

    # X-Frame-Options / X-XSS-Protection (old but still used)
    if soup.find("meta", attrs={"http-equiv": "X-Frame-Options"}):
        sec["score"] += 15
    if soup.find("meta", attrs={"http-equiv": "X-XSS-Protection"}):
        sec["score"] += 10

    sec["score"] = min(100, sec["score"])

    # ────────────────────────────────────────────────
    # 4) Content Score (max 100)
    # ────────────────────────────────────────────────
    cont = breakdown["content"]

    text = soup.get_text(separator=" ", strip=True)
    words = re.findall(r'\b\w+\b', text)
    word_count = len(words)

    cont["score"] = 0

    if 300 <= word_count <= 2000:
        cont["score"] += 40
    elif word_count > 2000:
        cont["score"] += 30
        cont["issues"].append("Very high word count – consider breaking into subpages")
    else:
        cont["issues"].append(f"Low content volume ({word_count} words)")

    # Internal links
    internal_links = [
        a["href"] for a in soup.find_all("a", href=True)
        if urlparse(urljoin(url, a["href"])).netloc == base_domain
    ]
    if len(internal_links) >= 8:
        cont["score"] += 30
    elif len(internal_links) >= 3:
        cont["score"] += 15
    else:
        cont["issues"].append(f"Low internal linking ({len(internal_links)} internal links)")

    # Heading hierarchy (very basic)
    headings = len(soup.find_all(["h2", "h3", "h4", "h5", "h6"]))
    if headings >= 3:
        cont["score"] += 20
    elif headings == 0:
        cont["issues"].append("No subheadings found")

    cont["score"] = min(100, cont["score"])

    # ────────────────────────────────────────────────
    # Final total & grade
    # ────────────────────────────────────────────────
    # Weighted average – SEO & Content more important
    total_score = int(
        (breakdown["seo"]["score"] * 0.35) +
        (breakdown["performance"]["score"] * 0.25) +
        (breakdown["security"]["score"] * 0.15) +
        (breakdown["content"]["score"] * 0.25)
    )

    if total_score >= 90:
        grade = "A+"
    elif total_score >= 80:
        grade = "A"
    elif total_score >= 70:
        grade = "B"
    elif total_score >= 60:
        grade = "C"
    else:
        grade = "D"

    return {
        "overall_score": total_score,
        "grade": grade,
        "breakdown": breakdown,
    }
