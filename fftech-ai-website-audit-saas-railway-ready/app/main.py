# app/main.py
import os
import logging
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FFTech_Main")

app = FastAPI(title="FFTech AI Website Audit")

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def root():
    index = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="index.html not found")

@app.get("/debug")
async def debug_info():
    try:
        cwd = os.getcwd()
        templates_abs = os.path.abspath(TEMPLATES_DIR)
        static_abs = os.path.abspath(STATIC_DIR)
        index_path = os.path.join(templates_abs, "index.html")

        return {
            "status": "backend running",
            "cwd": cwd,
            "templates_dir": TEMPLATES_DIR,
            "templates_dir_exists": os.path.exists(TEMPLATES_DIR),
            "templates_absolute": templates_abs,
            "index_file_exists": os.path.exists(index_path),
            "index_file_size": os.path.getsize(index_path) if os.path.exists(index_path) else "missing",
            "static_dir": STATIC_DIR,
            "static_dir_exists": os.path.exists(STATIC_DIR),
            "static_absolute": static_abs,
            "files_in_static": os.listdir(STATIC_DIR) if os.path.exists(STATIC_DIR) else "missing",
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str, request: Request):
    if full_path.startswith(("ws/", "api/", "openapi.json", "docs", "redoc", "debug", "static/")):
        raise HTTPException(status_code=404, detail="Not found")

    requested_static = os.path.join(STATIC_DIR, full_path)
    if os.path.isfile(requested_static):
        return FileResponse(requested_static)

    index = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.isfile(index):
        logger.info(f"Serving SPA fallback for /{full_path}")
        return FileResponse(index)

    raise HTTPException(status_code=404, detail="Not found")

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
