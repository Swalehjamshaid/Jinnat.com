def run_seo_audit(crawl_obj):
    pages = crawl_obj.pages if hasattr(crawl_obj, 'pages') else []
    
    if not pages:
        return {"score": 0.0, "metrics": {"error": "No pages crawled"}, "color": "#EF4444"}

    metrics = {}

    # Status
    metrics["21_HTTP_2xx"] = len([p for p in pages if 200 <= p.get('status_code', 0) < 300])
    metrics["23_HTTP_4xx"] = len([p for p in pages if 400 <= p.get('status_code', 0) < 500])
    metrics["24_HTTP_5xx"] = len([p for p in pages if 500 <= p.get('status_code', 0) < 600])

    # Titles
    titles = [p.get('title') for p in pages if p.get('title')]
    metrics["41_Missing_Titles"] = len(pages) - len(titles)
    metrics["42_Duplicate_Titles"] = len(titles) - len(set(titles)) if titles else 0

    # H1
    metrics["49_Missing_H1"] = len([p for p in pages if not p.get('h1_tags')])
    metrics["50_Multiple_H1"] = len([p for p in pages if len(p.get('h1_tags', [])) > 1])

    # Meta descriptions
    meta_descs = [p.get('meta_description') for p in pages if p.get('meta_description')]
    metrics["43_Missing_Meta_Descriptions"] = len(pages) - len(meta_descs)

    # Word count
    word_counts = [p.get('word_count', 0) for p in pages]
    metrics["45_Thin_Content_Pages"] = len([wc for wc in word_counts if wc < 300])

    # Safe robots & canonical
    robots_values = [p.get('robots_meta') for p in pages if p.get('robots_meta') is not None]
    metrics["Robots_NoIndex_Pages"] = sum(1 for v in robots_values if v and 'noindex' in str(v).lower())

    canonicals = [p.get('canonical') for p in pages if p.get('canonical') is not None]
    metrics["Canonical_Missing"] = len(pages) - len(canonicals)

    # Balanced penalties (less harsh on small crawls)
    penalties = 0
    n = max(1, len(pages))  # avoid division by zero

    penalties += metrics["41_Missing_Titles"] * 12
    penalties += metrics["43_Missing_Meta_Descriptions"] * 8
    penalties += metrics["49_Missing_H1"] * 6
    penalties += metrics["50_Multiple_H1"] * 4
    penalties += metrics["45_Thin_Content_Pages"] * 3
    penalties += metrics["Canonical_Missing"] * 5
    penalties += metrics["Robots_NoIndex_Pages"] * 6

    # Normalize penalties by page count (small crawls less penalized)
    score = max(0, 100 - (penalties / n))
    score = min(100, score)

    return {
        "score": round(score, 2),
        "metrics": metrics,
        "color": "#4F46E5"
    }
