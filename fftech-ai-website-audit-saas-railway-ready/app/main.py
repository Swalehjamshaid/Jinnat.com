import os
import logging
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FFTech_Main")

app = FastAPI(title="FFTech AI Website Audit")

# ────────────────────────────────────────────────
# Create the folder automatically if it doesn't exist
# This prevents the startup crash
# (you still need to add index.html later via git or build step)
STATIC_DIR = "static"
os.makedirs(STATIC_DIR, exist_ok=True)

# Mount the static files
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

# ────────────────────────────────────────────────
# Debug endpoint → visit /debug after deploy
@app.get("/debug")
async def debug_info():
    try:
        files = os.listdir(STATIC_DIR) if os.path.exists(STATIC_DIR) else []
        index_path = os.path.join(STATIC_DIR, "index.html")
        return {
            "status": "app is running",
            "working_dir": os.getcwd(),
            "static_dir": STATIC_DIR,
            "static_exists": os.path.isdir(STATIC_DIR),
            "index_exists": os.path.exists(index_path),
            "files_in_static": files,
            "index_size_bytes": os.path.getsize(index_path) if os.path.exists(index_path) else 0
        }
    except Exception as e:
        return {"error": str(e)}

# ────────────────────────────────────────────────
# Catch-all fallback (important for SPA / client-side routes)
@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    if full_path.startswith(("ws/", "debug", "openapi.json", "docs", "redoc")):
        raise HTTPException(status_code=404, detail="Not found")

    requested = os.path.join(STATIC_DIR, full_path)
    
    if os.path.isfile(requested):
        return FileResponse(requested)

    # fallback to index.html
    index = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)

    raise HTTPException(status_code=404, detail="Not found")

# ────────────────────────────────────────────────
# Your WebSocket endpoint
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
