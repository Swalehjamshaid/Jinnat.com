# app/main.py
import os
import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.audit.runner import WebsiteAuditRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(title="FF Tech Website Audit Engine")

# --------------------------------------------------
# Resolve BASE directory safely (Docker/Railway safe)
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"

# --------------------------------------------------
# Mount static files ONLY if folder exists
# --------------------------------------------------
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
else:
    logger.warning("Static directory not found:", STATIC_DIR)

# --------------------------------------------------
# Home Route
# --------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def home():
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)
    return HTMLResponse(
        content="""
        <h2>Frontend not found</h2>
        <p>index.html is missing.</p>
        <p>Expected path:</p>
        <pre>app/static/index.html</pre>
        """,
        status_code=500
    )

# --------------------------------------------------
# Health Check
# --------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}

# --------------------------------------------------
# Run Audit (REAL)
# --------------------------------------------------
@app.get("/api/audit")
async def run_audit(url: str = Query(...)):
    try:
        runner = WebsiteAuditRunner(url)

        if asyncio.iscoroutinefunction(runner.run):
            result = await runner.run()
        else:
            result = await asyncio.to_thread(runner.run)

        return JSONResponse(content=result)

    except Exception as e:
        logger.exception("Audit failed")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# --------------------------------------------------
# Entrypoint
# --------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
