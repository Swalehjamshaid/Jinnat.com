# app/main.py
import os
import asyncio
import logging
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.audit.runner import WebsiteAuditRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(title="FF Tech Website Audit Engine")

# --------------------------------------------------
# Static Frontend
# --------------------------------------------------
# Folder structure:
# app/
# ├─ main.py
# ├─ static/
# │   └─ index.html
# └─ audit/

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve frontend UI"""
    return FileResponse("app/static/index.html")


# --------------------------------------------------
# Health Check (important for containers)
# --------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": "audit-engine"}


# --------------------------------------------------
# Run Website Audit (REAL)
# --------------------------------------------------
@app.get("/api/audit")
async def run_audit(
    url: str = Query(..., description="Website URL to audit")
):
    """
    Runs the real website audit and returns full result
    """
    try:
        logger.info(f"Starting audit for {url}")

        runner = WebsiteAuditRunner(url)

        # If runner is async
        if asyncio.iscoroutinefunction(runner.run):
            result = await runner.run()
        else:
            # Sync fallback
            result = await asyncio.to_thread(runner.run)

        logger.info("Audit completed")

        return JSONResponse(content=result)

    except Exception as e:
        logger.exception("Audit failed")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# --------------------------------------------------
# App Entrypoint
# --------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )
