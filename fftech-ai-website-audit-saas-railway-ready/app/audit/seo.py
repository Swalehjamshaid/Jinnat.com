def run_seo_audit(crawl_obj):
    """
    Performs SEO audit based on crawled pages.
    Returns score (0-100), detailed metrics, and color.
    """
    pages = crawl_obj.pages if hasattr(crawl_obj, 'pages') else []
    
    if not pages:
        return {
            "score": 0.0,
            "metrics": {"error": "No pages crawled"},
            "color": "#EF4444"
        }

    # ────────────────────────────────────────────────
    # Collect & count key SEO issues
    # ────────────────────────────────────────────────
    metrics = {}

    # Status codes
    metrics["21_HTTP_2xx"] = len([p for p in pages if 200 <= p.get('status_code', 0) < 300])
    metrics["22_HTTP_3xx"] = len([p for p in pages if 300 <= p.get('status_code', 0) < 400])
    metrics["23_HTTP_4xx"] = len([p for p in pages if 400 <= p.get('status_code', 0) < 500])
    metrics["24_HTTP_5xx"] = len([p for p in pages if 500 <= p.get('status_code', 0) < 600])

    # Titles
    titles = [p.get('title') for p in pages if p.get('title')]
    metrics["41_Missing_Titles"] = len(pages) - len(titles)
    metrics["42_Duplicate_Titles"] = len(titles) - len(set(titles)) if titles else 0

    # H1 tags
    metrics["49_Missing_H1"] = len([p for p in pages if not p.get('h1_tags')])
    metrics["50_Multiple_H1"] = len([p for p in pages if len(p.get('h1_tags', [])) > 1])

    # Meta descriptions
    meta_descs = [p.get('meta_description') for p in pages if p.get('meta_description')]
    metrics["43_Missing_Meta_Descriptions"] = len(pages) - len(meta_descs)
    metrics["44_Duplicate_Meta_Descriptions"] = len(meta_descs) - len(set(meta_descs)) if meta_descs else 0

    # Word count / content length (basic thin content detection)
    word_counts = [p.get('word_count', 0) for p in pages]
    metrics["45_Thin_Content_Pages"] = len([wc for wc in word_counts if wc < 150])

    # ────────────────────────────────────────────────
    # Canonicals & Robots meta (FIXED: safe handling of None)
    # ────────────────────────────────────────────────
    canonicals = [p.get('canonical') for p in pages if p.get('canonical') is not None]
    metrics["Canonical_Missing"] = len(pages) - len(canonicals)

    # Safe robots meta check - avoid .lower() on None
    robots_values = [p.get('robots_meta') for p in pages if p.get('robots_meta') is not None]
    no_index_count = sum(1 for v in robots_values if v and 'noindex' in str(v).lower())
    metrics["Robots_NoIndex_Pages"] = no_index_count

    # ────────────────────────────────────────────────
    # Calculate SEO score (more balanced penalties)
    # ────────────────────────────────────────────────
    penalties = 0

    # Critical issues (heavy penalty)
    penalties += metrics["41_Missing_Titles"] * 12
    penalties += metrics["43_Missing_Meta_Descriptions"] * 10
    penalties += metrics["23_HTTP_4xx"] * 8

    # Medium issues
    penalties += metrics["49_Missing_H1"] * 6
    penalties += metrics["50_Multiple_H1"] * 4
    penalties += metrics["42_Duplicate_Titles"] * 3
    penalties += metrics["44_Duplicate_Meta_Descriptions"] * 3

    # Minor / content issues
    penalties += metrics["45_Thin_Content_Pages"] * 2

    # Additional from canonical & robots
    penalties += metrics["Canonical_Missing"] * 5
    penalties += metrics["Robots_NoIndex_Pages"] * 8  # Noindex hurts SEO visibility

    # Server errors (very bad)
    penalties += metrics["24_HTTP_5xx"] * 15

    # Final score (clamp between 0–100)
    score = max(0, 100 - penalties)
    score = min(100, score)

    return {
        "score": round(score, 2),
        "metrics": metrics,
        "color": "#4F46E5"
    }
