import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse


def grade_website(html: str, url: str) -> dict:
    """
    World-class deterministic website audit grader.
    No caching. No globals. No static scores.
    """

    soup = BeautifulSoup(html, "html.parser")

    breakdown = {}

    # ─────────────────────────────────
    # 1. BASIC SEO CHECKS
    # ─────────────────────────────────
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else ""

    h1_tags = soup.find_all("h1")
    images = soup.find_all("img")
    images_without_alt = [img for img in images if not img.get("alt")]

    seo_score = 0
    seo_issues = []

    if title:
        seo_score += 15
    else:
        seo_issues.append("Missing <title> tag")

    if meta_desc:
        seo_score += 15
    else:
        seo_issues.append("Missing meta description")

    if len(h1_tags) == 1:
        seo_score += 10
    elif len(h1_tags) == 0:
        seo_issues.append("No H1 tag found")
    else:
        seo_issues.append("Multiple H1 tags found")

    if images:
        alt_ratio = (len(images) - len(images_without_alt)) / len(images)
        seo_score += int(10 * alt_ratio)
    else:
        seo_score += 5

    breakdown["seo"] = {
        "score": seo_score,
        "issues": seo_issues,
    }

    # ─────────────────────────────────
    # 2. PERFORMANCE CHECKS
    # ─────────────────────────────────
    scripts = soup.find_all("script")
    stylesheets = soup.find_all("link", rel="stylesheet")

    perf_score = 100
    perf_issues = []

    if len(scripts) > 20:
        perf_score -= 15
        perf_issues.append("Too many JavaScript files")

    if len(stylesheets) > 10:
        perf_score -= 10
        perf_issues.append("Too many CSS files")

    if not soup.find("meta", attrs={"name": "viewport"}):
        perf_score -= 15
        perf_issues.append("Missing viewport meta tag")

    breakdown["performance"] = {
        "score": max(perf_score, 0),
        "issues": perf_issues,
    }

    # ─────────────────────────────────
    # 3. SECURITY CHECKS
    # ─────────────────────────────────
    parsed_url = urlparse(url)
    security_score = 0
    security_issues = []

    if parsed_url.scheme == "https":
        security_score += 30
    else:
        security_issues.append("Website is not using HTTPS")

    if soup.find("meta", attrs={"http-equiv": "Content-Security-Policy"}):
        security_score += 20
    else:
        security_issues.append("Missing Content Security Policy")

    if soup.find("meta", attrs={"http-equiv": "X-Frame-Options"}):
        security_score += 10
    else:
        security_issues.append("Missing X-Frame-Options")

    breakdown["security"] = {
        "score": security_score,
        "issues": security_issues,
    }

    # ─────────────────────────────────
    # 4. CONTENT QUALITY
    # ─────────────────────────────────
    text = soup.get_text(separator=" ")
    words = re.findall(r"\b\w+\b", text)

    content_score = 0
    content_issues = []

    if len(words) > 300:
        content_score += 30
    else:
        content_issues.append("Low text content on page")

    internal_links = [
        a for a in soup.find_all("a", href=True)
        if parsed_url.netloc in a["href"]
    ]

    if len(internal_links) >= 5:
        content_score += 20
    else:
        content_issues.append("Low internal linking")

    breakdown["content"] = {
        "score": content_score,
        "issues": content_issues,
    }

    # ─────────────────────────────────
    # 5. FINAL SCORE CALCULATION
    # ─────────────────────────────────
    total_score = (
        breakdown["seo"]["score"]
        + breakdown["performance"]["score"]
        + breakdown["security"]["score"]
        + breakdown["content"]["score"]
    )

    total_score = min(int(total_score / 4), 100)

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
