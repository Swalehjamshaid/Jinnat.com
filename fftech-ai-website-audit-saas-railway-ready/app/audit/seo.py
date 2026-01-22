def run_seo_audit(crawl_obj):
    pages = crawl_obj.pages
    metrics = {
        "21_HTTP_2xx": len([p for p in pages if 200 <= p['status_code'] < 300]),
        "41_Missing_Titles": len([p for p in pages if not p['title']]),
        "42_Duplicate_Titles": len(pages) - len(set([p['title'] for p in pages if p['title']])),
        "49_Missing_H1": len([p for p in pages if not p['h1_tags']]),
        "50_Multiple_H1": len([p for p in pages if len(p['h1_tags']) > 1])
    }
    score = max(0, 100 - (metrics["41_Missing_Titles"] * 10 + metrics["49_Missing_H1"] * 5))
    return {"score": round(score, 2), "metrics": metrics, "color": "#4F46E5"}
