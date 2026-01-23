import httpx
import logging
import os
import asyncio
import certifi
import ssl
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.services.ai_service import AIService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AuditEngine")

class AuditMetrics(BaseModel):
    """Pydantic V2 Model for Data Integrity."""
    overall_score: float = Field(..., ge=0, le=1)
    fcp: str
    lcp: str
    cls: str
    model_config = ConfigDict(from_attributes=True)

class WebsiteGrader:
    def __init__(self):
        self.api_key = os.getenv("PSI_API_KEY")
        self.psi_endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.ai_service = AIService()

    async def validate_connectivity(self, url: str) -> Dict[str, Any]:
        """Reliability Check with SSL Fallback for sites like haier.com.pk."""
        async with httpx.AsyncClient(verify=self.ssl_context, timeout=15.0) as client:
            try:
                response = await client.get(url)
                return {"status": "SUCCESS", "detail": "Secure", "error_code": None}
            except Exception:
                async with httpx.AsyncClient(verify=False, timeout=15.0) as insecure:
                    try:
                        await insecure.get(url)
                        return {"status": "WARNING", "detail": "SSL_BYPASSED", "error_code": "SSL_001"}
                    except Exception:
                        return {"status": "FAILURE", "detail": "OFFLINE", "error_code": "NET_404"}

    async def fetch_performance(self, url: str) -> Optional[AuditMetrics]:
        if not self.api_key: return None
        params = {"url": url, "key": self.api_key, "category": "PERFORMANCE"}
        
        async with httpx.AsyncClient(verify=self.ssl_context, timeout=45.0) as client:
            try:
                response = await client.get(self.psi_endpoint, params=params)
                if response.status_code != 200: return None
                
                data = response.json()
                lh = data.get("lighthouseResult", {})
                audits = lh.get("audits", {})
                return AuditMetrics(
                    overall_score=lh.get("categories", {}).get("performance", {}).get("score", 0),
                    fcp=audits.get("first-contentful-paint", {}).get("displayValue", "N/A"),
                    lcp=audits.get("largest-contentful-paint", {}).get("displayValue", "N/A"),
                    cls=audits.get("cumulative-layout-shift", {}).get("displayValue", "N/A")
                )
            except Exception: return None

    async def run_full_audit(self, url: str) -> Dict[str, Any]:
        if not url.startswith('http'): url = f"https://{url}"
        start_time = datetime.now(timezone.utc)
        
        conn_task = asyncio.create_task(self.validate_connectivity(url))
        perf_task = asyncio.create_task(self.fetch_performance(url))
        conn_res, perf_res = await asyncio.gather(conn_task, perf_task)
        
        report = {
            "url": url,
            "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "duration": 0},
            "connectivity": conn_res,
            "performance": perf_res.model_dump() if perf_res else None,
            "score": round(perf_res.overall_score * 100, 2) if perf_res else 0
        }
        
        report["ai_summary"] = await self.ai_service.generate_audit_summary(report)
        report["metadata"]["duration"] = round((datetime.now(timezone.utc) - start_time).total_seconds(), 2)
        return report
