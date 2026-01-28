# app/main.py
import os
import asyncio
import logging
from typing import Dict, Any
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from app.audit.runner import WebsiteAuditRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit")

app = FastAPI(title="FF Tech Audit Engine", version="1.0")


# --------------------------------------------------
# Root (always safe)
# --------------------------------------------------
@app.get("/")
async def root():
    return {
        "service": "FF Tech Audit Engine",
        "status": "running",
        "endpoints": {
            "audit": "/api/audit?url=https://example.com",
            "health": "/health"
        }
    }


# --------------------------------------------------
# Health
# --------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


# --------------------------------------------------
# Audit Endpoint (schema-free)
# --------------------------------------------------
@app.get("/api/audit")
async def audit(url: str = Query(..., description="Website URL")):
    """
    Returns ANY JSON produced by WebsiteAuditRunner
    Frontend auto-adapts to this payload
    """
    try:
        logger.info(f"Audit started: {url}")
        runner = WebsiteAuditRunner(url)

        if asyncio.iscoroutinefunction(runner.run):
            result: Dict[str, Any] = await runner.run()
        else:
            result: Dict[str, Any] = await asyncio.to_thread(runner.run)

        # Inject meta (safe, optional)
        result.setdefault("_meta", {})
        result["_meta"].update({
            "engine": "FF Tech Audit Engine",
            "url": url
        })

        logger.info("Audit finished")
        return JSONResponse(content=result)

    except Exception as e:
        logger.exception("Audit failed")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Audit failed",
                "message": str(e)
            }
        )


# --------------------------------------------------
# Entrypoint
# --------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
