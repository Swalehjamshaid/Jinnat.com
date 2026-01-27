import os
import logging
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FFTech_Main")

app = FastAPI(title="FFTech AI Website Audit")

# Calculate absolute path to static folder (more reliable on Railway / containers)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Debug endpoint – visit /debug after deploy to see real situation
@app.get("/debug")
async def debug_paths():
    try:
        return {
            "status": "app loaded",
            "current_working_dir": os.getcwd(),
            "base_dir": BASE_DIR,
            "static_dir_absolute": STATIC_DIR,
            "static_dir_exists": os.path.isdir(STATIC_DIR),
            "index_html_exists": os.path.isfile(os.path.join(STATIC_DIR, "index.html")),
            "files_in_static": os.listdir(STATIC_DIR) if os.path.isdir(STATIC_DIR) else "directory missing"
        }
    except Exception as e:
        return {"debug_error": str(e)}

# Mount static files
# Use check_dir=False TEMPORARILY only if desperate (not recommended long-term)
# Best fix = make sure static/ folder exists in git
app.mount(
    "/",
    StaticFiles(
        directory=STATIC_DIR,
        html=True,
        # check_dir=False   # ← uncomment ONLY for quick test, then remove
    ),
    name="static"
)

# Catch-all fallback for SPA / client routing (optional but useful)
@app.get("/{full_path:path}")
async def catch_all(full_path: str, request: Request):
    if full_path.startswith(("ws/", "debug", "openapi.json", "docs", "redoc")):
        raise HTTPException(status_code=404, detail="Not found")

    requested_path = os.path.join(STATIC_DIR, full_path)
    
    if os.path.isfile(requested_path):
        return FileResponse(requested_path)

    # Fallback to index.html
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_path):
        logger.info(f"Fallback to index.html for: /{full_path}")
        return FileResponse(index_path)

    raise HTTPException(status_code=404, detail="Not found")

# ────────────────────────────────────────────────
# Your WebSocket endpoint (unchanged)
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

# No need for if __name__ == "__main__" on Railway – Nixpacks/Uvicorn handles it
