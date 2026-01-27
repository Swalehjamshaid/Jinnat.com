import os
import logging
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FFTech_Main")

app = FastAPI(title="FFTech AI Website Audit")

# ── Adjust this path depending on your build output ─────────────────────────────
# Most common options:
# - If you copy build files into /static           → "static"
# - If frontend is in repo root and builds to dist → "dist" or "frontend/dist"
# - Recommended: point directly to build output (no copy needed)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")          # ← change to "dist" if needed

# Create folder only if you generate files at runtime (usually not needed)
# os.makedirs(STATIC_DIR, exist_ok=True)

# Mount static files (js, css, images, etc.) + enable SPA index fallback
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

# Optional: Catch-all fallback for SPA client-side routing
# (handles /dashboard, /results/abc, etc. by serving index.html)
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_catch_all(full_path: str):
    # Protect API & websocket paths from being caught
    if full_path.startswith(("api/", "docs", "redoc", "ws/", "openapi.json")):
        raise HTTPException(status_code=404, detail="Not found")

    # Try to serve requested file if it exists (e.g. /assets/logo.png)
    file_path = os.path.join(STATIC_DIR, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    # Otherwise → serve index.html (SPA router will handle the path)
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.isfile(index_path):
        logger.error(f"index.html not found in {STATIC_DIR}")
        raise HTTPException(status_code=500, detail="index.html missing - frontend build failed or wrong path")

    return FileResponse(index_path)


@app.websocket("/ws/audit-progress")
async def audit_progress(websocket: WebSocket):
    await websocket.accept()
    url = websocket.query_params.get("url")
    if not url:
        await websocket.send_json({"error": "URL not provided", "finished": True})
        await websocket.close()
        return

    try:
        from app.audit.runner import WebsiteAuditRunner
        runner = WebsiteAuditRunner(url)

        async def progress_callback(data: dict):
            await websocket.send_json(data)

        await runner.run_audit(progress_callback)
    except Exception as e:
        logger.exception("Audit failed")
        await websocket.send_json({"error": str(e), "finished": True})
    finally:
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
