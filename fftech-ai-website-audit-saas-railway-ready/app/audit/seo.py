import logging
from bs4 import BeautifulSoup

logger = logging.getLogger("audit_engine")

async def analyze_onpage(pages: list):
    """Advanced on-page SEO scoring – more balanced & detailed."""
    if not pages:
        logger.warning("No pages provided for on-page SEO analysis")
        return {"score": 0, "issues": ["No crawlable pages found"], "details": {}}

    total_score = 0
    total_pages = 0
    all_issues = []
    page_details = []  # For future breakdown display

    for page in pages:
        url = page.get("url", "unknown")
        html = page.get("html", "").strip()
        if not html:
            all_issues.append(f"No HTML content for {url}")
            continue

        total_pages += 1
        soup = BeautifulSoup(html, "lxml")
        page_score = 0   # Start from 0 and add points (easier to understand)

        issues = []
        detail = {"url": url, "score": 0, "checks": {}}

        # 1. Title (max 15 points)
        title_tag = soup.find("title")
        if title_tag and title_tag.string and len(title_tag.string.strip()) >= 10:
            page_score += 15
            detail["checks"]["title"] = "Present & reasonable length"
        else:
            issues.append(f"Missing or empty title tag on {url}")
            detail["checks"]["title"] = "Missing/empty"

        # 2. Meta description (max 15 points)
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content") and 50 <= len(meta_desc["content"].strip()) <= 160:
            page_score += 15
            detail["checks"]["meta_description"] = "Present & good length"
        else:
            issues.append(f"Missing or poor meta description on {url}")
            detail["checks"]["meta_description"] = "Missing/too short/long"

        # 3. Headings structure (max 20 points)
        h1_count = len(soup.find_all("h1"))
        if h1_count == 1:
            page_score += 15
            detail["checks"]["h1"] = "Exactly one H1 – good"
        elif h1_count > 1:
            page_score += 5
            issues.append(f"Multiple H1 tags ({h1_count}) on {url}")
            detail["checks"]["h1"] = f"Multiple ({h1_count})"
        else:
            issues.append(f"No H1 tag on {url}")
            detail["checks"]["h1"] = "Missing"

        # 4. Image alt texts (max 15 points)
        images = soup.find_all("img")
        if images:
            with_alt = sum(1 for img in images if img.get("alt") and img["alt"].strip())
            alt_ratio = with_alt / len(images) if images else 1
            page_score += int(15 * alt_ratio)
            missing = len(images) - with_alt
            if missing > 0:
                issues.append(f"{missing}/{len(images)} images missing alt text on {url}")
            detail["checks"]["image_alt"] = f"{with_alt}/{len(images)} have alt"

        # 5. Basic content signals (max 20 points)
        text_content = soup.get_text(separator=" ", strip=True)
        word_count = len(text_content.split())
        if word_count > 300:
            page_score += 15
        elif word_count > 100:
            page_score += 8
        detail["checks"]["content_words"] = word_count

        # 6. Canonical & robots (bonus 5 points each)
        if soup.find("link", rel="canonical"):
            page_score += 5
            detail["checks"]["canonical"] = "Present"
        if soup.find("meta", attrs={"name": "robots"}):
            page_score += 5
            detail["checks"]["robots_meta"] = "Present"

        page_score = min(page_score, 100)  # Cap
        total_score += page_score
        page_details.append(detail)
        all_issues.extend(issues)

    if total_pages == 0:
        return {"score": 0, "issues": ["No valid HTML pages processed"], "details": {}}

    avg_score = round(total_score / total_pages)
    logger.info(f"On-page SEO average score: {avg_score} across {total_pages} pages")

    return {
        "score": avg_score,
        "issues": all_issues[:20],          # Limit to top issues
        "details": {
            "average": avg_score,
            "pages": page_details
        }
    }
