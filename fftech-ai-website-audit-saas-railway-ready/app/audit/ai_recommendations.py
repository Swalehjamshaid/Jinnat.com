# app/audit/ai_recommendations.py

def generate_ai_recommendations(seo_metrics: dict, performance_metrics: dict):
    """
    Generate AI recommendations based on SEO & performance metrics.
    Placeholder version – replace with real AI logic.
    """
    recommendations = []

    # Example SEO recommendations
    if seo_metrics.get("41_Missing_Titles", 0) > 0:
        recommendations.append("Add missing page titles.")

    if seo_metrics.get("43_Missing_Meta_Descriptions", 0) > 0:
        recommendations.append("Add meta descriptions to pages missing them.")

    # Example Performance recommendations
    lcp = performance_metrics.get("LCP_ms", 0)
    if lcp and lcp > 2500:
        recommendations.append("Optimize LCP by improving server response and image loading.")

    cls = performance_metrics.get("CLS", 0)
    if cls and cls > 0.1:
        recommendations.append("Fix layout shifts to reduce CLS.")

    tbt = performance_metrics.get("TBT_ms", 0)
    if tbt and tbt > 200:
        recommendations.append("Reduce TBT by minimizing JS execution.")

    return recommendations
