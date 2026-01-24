# app/audit/runner.py
import logging
from ..settings import get_settings  # CRITICAL FIX: The missing import
from .psi import fetch_psi

logger = logging.getLogger("audit_runner")

async def run_audit(url: str):
    settings = get_settings()
    logger.info(f"Auditing: {url}")
    
    # Use the Railway variable for the Google API
    psi_data = fetch_psi(url, api_key=settings.PSI_API_KEY)
    
    # Process scores (simplified for brevity)
    perf_score = 0
    if psi_data and 'lighthouseResult' in psi_data:
        perf_score = psi_data['lighthouseResult']['categories']['performance']['score'] * 100

    return {
        "url": url,
        "overall_score": round(perf_score, 2),
        "grade": "A" if perf_score > 85 else "B" if perf_score > 60 else "D",
        "breakdown": {
            "onpage": 100.0,
            "performance": round(perf_score, 2),
            "coverage": 0,
            "confidence": 95
        }
    }
