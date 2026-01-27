import os
import logging
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FFTech_Main")

app = FastAPI(title="FFTech AI Website Audit")

# Use relative path - this is correct for Railway
STATIC_DIR = "static"

# Mount static files at root level
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

# Optional debug endpoint - helps you see what Railway actually sees
@app.get("/debug")
async def debug_info():
    try:
        return {
            "status": "app loaded",
            "working_directory": os.getcwd(),
            "static_directory": STATIC_DIR,
            "static_exists": os.path.isdir(STATIC_DIR),
            "index_exists": os.path.isfile(os.path.join(STATIC_DIR, "index.html")),
            "files_in_static": os.listdir(STATIC_DIR) if os.path.isdir(STATIC_DIR) else "folder missing"
        }
    except Exception as e:
        return {"debug_error": str(e)}

# Catch-all route to serve index.html for unknown paths (SPA style)
@app.get("/{full_path:path}")
async def catch_all(full_path: str, request: Request):
    if full_path.startswith(("ws/", "debug", "openapi.json", "docs", "redoc")):
        raise HTTPException(status_code=404, detail="Not found")

    requested_file = os.path.join(STATIC_DIR, full_path)

    if os.path.isfile(requested_file):
        return FileResponse(requested_file)

    # fallback to index.html
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)

    raise HTTPException(status_code=404, detail="Not found")

# Your websocket endpoint
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
