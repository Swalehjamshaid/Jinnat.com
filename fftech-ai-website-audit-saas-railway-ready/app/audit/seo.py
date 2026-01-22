def run_seo_audit(crawl_obj):
    pages = crawl_obj.pages if hasattr(crawl_obj, 'pages') else []

    if not pages:
        return {
            "score": 0.0,
            "metrics": {"error": "No pages crawled"},
            "color": "#EF4444"
        }

    metrics = {}

    # ────────────────────────────────────────────────
    # HTTP Status
    # ────────────────────────────────────────────────
    metrics["21_HTTP_2xx"] = sum(1 for p in pages if 200 <= (p.get("status_code") or 0) < 300)
    metrics["23_HTTP_4xx"] = sum(1 for p in pages if 400 <= (p.get("status_code") or 0) < 500)
    metrics["24_HTTP_5xx"] = sum(1 for p in pages if 500 <= (p.get("status_code") or 0) < 600)

    # ────────────────────────────────────────────────
    # Titles
    # ────────────────────────────────────────────────
    titles = [
        str(p.get("title")).strip().lower()
        for p in pages if p.get("title")
    ]
    metrics["41_Missing_Titles"] = sum(1 for p in pages if not p.get("title"))
    metrics["42_Duplicate_Titles"] = max(0, len(titles) - len(set(titles)))

    # ────────────────────────────────────────────────
    # H1
    # ────────────────────────────────────────────────
    metrics["49_Missing_H1"] = sum(1 for p in pages if not p.get("h1_tags"))
    metrics["50_Multiple_H1"] = sum(1 for p in pages if len(p.get("h1_tags") or []) > 1)

    # ────────────────────────────────────────────────
    # Meta Descriptions
    # ────────────────────────────────────────────────
    metrics["43_Missing_Meta_Descriptions"] = sum(
        1 for p in pages if not p.get("meta_description")
    )

    # ────────────────────────────────────────────────
    # Thin Content (only indexable pages)
    # ────────────────────────────────────────────────
    metrics["45_Thin_Content_Pages"] = sum(
        1 for p in pages
        if (p.get("word_count", 0) < 300)
        and (200 <= (p.get("status_code") or 0) < 300)
    )

    # ────────────────────────────────────────────────
    # Robots & Canonical
    # ────────────────────────────────────────────────
    metrics["Robots_NoIndex_Pages"] = sum(
        1 for p in pages
        if p.get("robots_meta") and "noindex" in str(p.get("robots_meta")).lower()
    )

    metrics["Canonical_Missing"] = sum(
        1 for p in pages
        if (200 <= (p.get("status_code") or 0) < 300)
        and not p.get("canonical")
    )

    # ────────────────────────────────────────────────
    # Scoring Engine
    # ────────────────────────────────────────────────
    n = max(1, len(pages))
    penalties = 0

    penalties += metrics["41_Missing_Titles"] * 12
    penalties += metrics["43_Missing_Meta_Descriptions"] * 8
    penalties += metrics["49_Missing_H1"] * 6
    penalties += metrics["50_Multiple_H1"] * 4
    penalties += metrics["45_Thin_Content_Pages"] * 3
    penalties += metrics["Canonical_Missing"] * 5
    penalties += metrics["Robots_NoIndex_Pages"] * 6
    penalties += metrics["23_HTTP_4xx"] * 4
    penalties += metrics["24_HTTP_5xx"] * 8

    score = max(0, min(100, 100 - (penalties / n)))
    score = round(score, 2)

    # ────────────────────────────────────────────────
    # 🔥 ENTERPRISE ADDITIONS (NON-BREAKING)
    # ────────────────────────────────────────────────

    # SEO Grade
    seo_grade = (
        "A" if score >= 90 else
        "B" if score >= 80 else
        "C" if score >= 70 else
        "D" if score >= 60 else
        "F"
    )

    # Issue Severity Mapping
    issue_severity = {
        "critical": metrics["24_HTTP_5xx"] + metrics["Robots_NoIndex_Pages"],
        "high": metrics["41_Missing_Titles"] + metrics["49_Missing_H1"],
        "medium": metrics["43_Missing_Meta_Descriptions"] + metrics["Canonical_Missing"],
        "low": metrics["45_Thin_Content_Pages"]
    }

    # Page-Level Diagnostics
    page_diagnostics = []
    for p in pages:
        issues = []
        if not p.get("title"):
            issues.append("Missing title")
        if not p.get("meta_description"):
            issues.append("Missing meta description")
        if not p.get("h1_tags"):
            issues.append("Missing H1")
        if p.get("word_count", 0) < 300:
            issues.append("Thin content")
        if p.get("robots_meta") and "noindex" in str(p.get("robots_meta")).lower():
            issues.append("Noindex tag present")

        if issues:
            page_diagnostics.append({
                "url": p.get("url"),
                "issues": issues
            })

    # Opportunity Scoring (Quick Wins)
    opportunity_score = max(
        0,
        100
        - (metrics["41_Missing_Titles"] * 10)
        - (metrics["43_Missing_Meta_Descriptions"] * 8)
        - (metrics["49_Missing_H1"] * 6)
    )

    # AI-Based SEO Recommendations (Rule-Based, Safe)
    recommendations = []
    if metrics["41_Missing_Titles"] > 0:
        recommendations.append("Add unique, keyword-focused titles to all pages.")
    if metrics["43_Missing_Meta_Descriptions"] > 0:
        recommendations.append("Write compelling meta descriptions to improve CTR.")
    if metrics["45_Thin_Content_Pages"] > 0:
        recommendations.append("Expand thin pages with helpful, intent-matched content.")
    if metrics["Canonical_Missing"] > 0:
        recommendations.append("Add canonical tags to prevent duplicate content issues.")
    if metrics["Robots_NoIndex_Pages"] > 0:
        recommendations.append("Review noindex tags to ensure important pages are indexable.")

    # ────────────────────────────────────────────────
    # Final Output (Backward Compatible)
    # ────────────────────────────────────────────────
    return {
        "score": score,
        "metrics": metrics,
        "color": "#4F46E5",

        # ✅ ADDITIVE (Safe)
        "seo_grade": seo_grade,
        "issue_severity": issue_severity,
        "page_level_diagnostics": page_diagnostics,
        "opportunity_score": round(opportunity_score, 2),
        "ai_recommendations": recommendations
    }
