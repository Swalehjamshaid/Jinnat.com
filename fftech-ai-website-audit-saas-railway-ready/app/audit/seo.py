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
    metrics["Title_Length_Issues"] = len([t for t in titles if len(t) < 10 or len(t) > 60])

    # H1 tags
    metrics["49_Missing_H1"] = len([p for p in pages if not p.get('h1_tags')])
    metrics["50_Multiple_H1"] = len([p for p in pages if len(p.get('h1_tags', [])) > 1])

    # Meta descriptions
    meta_descs = [p.get('meta_description') for p in pages if p.get('meta_description')]
    metrics["43_Missing_Meta_Descriptions"] = len(pages) - len(meta_descs)
    metrics["44_Duplicate_Meta_Descriptions"] = len(meta_descs) - len(set(meta_descs)) if meta_descs else 0
    metrics["Meta_Length_Issues"] = len([m for m in meta_descs if len(m) < 50 or len(m) > 160])

    # Word count / content length
    word_counts = [p.get('word_count', 0) for p in pages]
    metrics["45_Thin_Content_Pages"] = len([wc for wc in word_counts if wc < 300])  # Updated threshold for 2026 standards

    # Canonicals
    canonicals = [p.get('canonical') for p in pages if p.get('canonical')]
    metrics["Canonical_Missing"] = len(pages) - len(canonicals)

    # Robots meta
    no_index = len([p for p in pages if p.get('robots_meta', '').lower() == 'noindex'])
    metrics["Robots_NoIndex_Pages"] = no_index

    # Penalties calculation (balanced for real audit)
    penalties = 0

    # Critical
    penalties += metrics["41_Missing_Titles"] * 15
    penalties += metrics["43_Missing_Meta_Descriptions"] * 12
    penalties += metrics["23_HTTP_4xx"] * 10
    penalties += metrics["24_HTTP_5xx"] * 20

    # Medium
    penalties += metrics["49_Missing_H1"] * 8
    metrics["50_Multiple_H1"] * 5
    penalties += metrics["45_Thin_Content_Pages"] * 6
    penalties += metrics["Canonical_Missing"] * 7

    # Minor
    penalties += metrics["42_Duplicate_Titles"] * 4
    penalties += metrics["44_Duplicate_Meta_Descriptions"] * 3
    penalties += metrics["Title_Length_Issues"] * 2
    penalties += metrics["Meta_Length_Issues"] * 2

    # Adjust for noindex (if many, penalty)
    if no_index > len(pages) * 0.2:
        penalties += (no_index / len(pages)) * 50

    score = max(0, min(100, 100 - penalties / len(pages)))

    return {
        "score": round(score, 2),
        "metrics": metrics,
        "color": "#4F46E5"
    }
