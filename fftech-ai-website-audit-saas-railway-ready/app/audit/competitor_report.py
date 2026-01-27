import logging
from urllib.parse import urlparse

logger = logging.getLogger("audit_engine")

def compare_with_competitors(url: str) -> dict:
    """
    Compare the target website with relevant competitors.
    Currently uses static competitor list for Pakistani appliance brands + simple heuristic scoring.
    Returns top competitor score and list for dashboard.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")

    # Define known competitors based on market (Pakistan home appliances / electronics)
    # Add more as needed; group by industry if you expand beyond appliances
    competitor_map = {
        "haier.com.pk": [
            {"name": "Dawlance", "domain": "dawlance.com.pk", "base_score": 88},
            {"name": "PEL", "domain": "pel.com.pk", "base_score": 85},
            {"name": "Waves", "domain": "waves.com.pk", "base_score": 78},
            {"name": "Orient", "domain": "orient.com.pk", "base_score": 82},
            {"name": "Gree", "domain": "gree.com.pk", "base_score": 80},
        ],
        # Add patterns for other domains if needed
        "default": [
            {"name": "Competitor A", "domain": "examplecompetitor.pk", "base_score": 85},
            {"name": "Competitor B", "domain": "another.pk", "base_score": 80},
        ]
    }

    # Select competitor list based on target domain
    competitors = competitor_map.get(domain, competitor_map["default"])

    if not competitors:
        logger.warning(f"No competitors defined for domain: {domain}")
        return {
            "top_competitor_score": 85,  # fallback
            "your_score_vs_top": 0,
            "competitors": []
        }

    # Simple heuristic score for "your" site (0-100)
    # In real version: integrate with SEO score, page count from crawler, domain age, etc.
    # For now: placeholder based on domain + random-ish variance
    your_estimated_score = 65  # default baseline
    if "haier" in domain:
        your_estimated_score = 72  # Haier is strong globally but local site may lag

    # Find top competitor score
    top_score = max(c["base_score"] for c in competitors)

    # Optional: Adjust top_score slightly based on your score (make it relative)
    relative_top = top_score - (top_score - your_estimated_score) * 0.1  # slight boost if you're close

    # Build response
    result = {
        "top_competitor_score": int(top_score),
        "your_score_vs_top": int(your_estimated_score),
        "competitors": [
            {
                "name": c["name"],
                "domain": c["domain"],
                "score": c["base_score"],
                "vs_your": c["base_score"] - your_estimated_score
            }
            for c in competitors
        ]
    }

    logger.info(f"Competitor comparison for {url}: top={top_score}, your_est={your_estimated_score}")
    return result
