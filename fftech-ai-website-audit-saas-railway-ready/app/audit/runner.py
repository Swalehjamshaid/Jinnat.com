# app/audit/runner.py
import logging
from app.audit.crawler import async_crawl

logger = logging.getLogger("audit_engine")

async def run_audit(url: str):
    """
    Run a full website audit.
    Returns a dictionary formatted for charts and the dashboard.
    """
    try:
        result = await async_crawl(url, max_pages=20)

        # Aggregate SEO metrics safely
        total_images_missing_alt = sum(r.get("seo", {}).get("images_missing_alt", 0) for r in result["report"])
        total_title_missing = sum(r.get("seo", {}).get("title_missing", 0) for r in result["report"])
        total_meta_missing = sum(r.get("seo", {}).get("meta_description_missing", 0) for r in result["report"])

        # Simple scoring logic (0–100)
        onpage_score = max(0, 100 - total_images_missing_alt*2 - total_title_missing*3 - total_meta_missing*2)
        performance_score = max(0, 100 - len(result["broken_internal"])*2)
        coverage_score = max(0, 100 - len(result["broken_external"])*1)
        confidence = int((onpage_score + performance_score + coverage_score) / 3)
        overall_score = int((onpage_score + performance_score + coverage_score + confidence)/4)
        grade = "A" if overall_score > 85 else "B" if overall_score > 70 else "C" if overall_score > 50 else "D"

        # Prepare chart-ready data
        chart_data = {
            "bar": {
                "labels": ["On-page SEO", "Performance", "Link Coverage", "AI Confidence"],
                "data": [onpage_score, performance_score, coverage_score, confidence],
                "colors": ["#0d6efd", "#10b981", "#f59e0b", "#ef4444"]
            },
            "radar": {
                "labels": ["Images Alt", "Title", "Meta Desc", "Internal Links", "External Links"],
                "data": [total_images_missing_alt, total_title_missing, total_meta_missing,
                         len(result["unique_internal"]), len(result["unique_external"])]
            },
            "doughnut": {
                "labels": ["Broken Internal", "Broken External"],
                "data": [len(result["broken_internal"]), len(result["broken_external"])],
                "colors": ["#ef4444", "#f59e0b"]
            }
        }

        return {
            "url": url,
            "overall_score": overall_score,
            "grade": grade,
            "breakdown": {
                "onpage": onpage_score,
                "performance": performance_score,
                "coverage": coverage_score,
                "confidence": confidence
            },
            "metrics": {
                "internal_links": len(result["report"]),
                "external_links": len(result["report"]),
                "broken_internal_links": len(result["broken_internal"]),
                "broken_external_links": len(result["broken_external"])
            },
            "chart_data": chart_data,
            "report": result["report"],
            "crawl_progress": int(len(result["report"])/max(1,20)*100)
        }

    except Exception as e:
        logger.exception(f"Audit failed for {url}: {e}")
        return {"error": str(e), "finished": True, "status": "Audit failed."}
