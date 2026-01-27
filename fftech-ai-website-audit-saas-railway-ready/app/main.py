import os
import logging
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FFTech_Main")

app = FastAPI(title="FFTech AI Website Audit")

# Use relative path – safer on PaaS like Railway
STATIC_DIR = "static"

# Mount the entire static folder at root
# html=True → auto-serve index.html for / and unknown directories
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

# Debug endpoint – visit /debug after deploy to see what's really there
@app.get("/debug")
async def debug_info():
    try:
        cwd = os.getcwd()
        static_abs = os.path.abspath(STATIC_DIR)
        index_path = os.path.join(static_abs, "index.html")
        
        return {
            "status": "backend running",
            "current_working_directory": cwd,
            "static_directory": STATIC_DIR,
            "static_directory_exists": os.path.exists(STATIC_DIR),
            "static_directory_absolute": static_abs,
            "index_file_exists": os.path.exists(index_path),
            "files_in_static": os.listdir(STATIC_DIR) if os.path.exists(STATIC_DIR) else "directory missing",
            "index_file_size": os.path.getsize(index_path) if os.path.exists(index_path) else "missing"
        }
    except Exception as e:
        return {"error": str(e)}

# Catch-all fallback (protects API routes + serves index.html for client paths)
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str, request: Request):
    # Skip special paths
    if full_path.startswith(("ws/", "api/", "debug", "openapi.json", "docs", "redoc")):
        raise HTTPException(status_code=404, detail="Not found")

    requested = os.path.join(STATIC_DIR, full_path)
    
    if os.path.isfile(requested):
        return FileResponse(requested)
    
    # Fallback to index.html
    index = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index):
        logger.info(f"Serving fallback index.html for path: /{full_path}")
        return FileResponse(index)
    
    raise HTTPException(status_code=404, detail="Not found")

# Your WebSocket (keep as-is)
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

# No uvicorn block needed – Railway runs it automatically via uvicorn main:app
