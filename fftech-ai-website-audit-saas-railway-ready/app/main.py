import os
import logging
from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FFTech_Main")

# Create the FastAPI app FIRST
app = FastAPI(title="FFTech AI Website Audit")

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Create the static folder if it doesn't exist (safe to do)
os.makedirs(STATIC_DIR, exist_ok=True)

# Mount static files at root (recommended for single-page apps / simple HTML)
# html=True enables automatic index.html serving for directories
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

# Root route - serves index.html directly (your original logic, improved)
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        logger.error("index.html missing in static/")
        return HTMLResponse(
            content="<h1>Deployment Error</h1><p>index.html missing in /static/</p><p>Make sure static/index.html exists in your repo.</p>",
            status_code=500
        )
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

# Catch-all fallback for SPA-style paths (important if you add client-side routing later)
# This serves index.html for any non-file path, but skips API/websocket paths
@app.get("/{full_path:path}", include_in_schema=False)
async def catch_all(full_path: str, request: Request):
    # Protect special paths
    if full_path.startswith(("ws/", "api/", "docs", "redoc", "openapi.json")):
        raise HTTPException(status_code=404, detail="Not found")

    requested_file = os.path.join(STATIC_DIR, full_path)
    if os.path.isfile(requested_file):
        return FileResponse(requested_file)

    # Fallback to index.html for client-side routing
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)

    raise HTTPException(status_code=404, detail="Not found")

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


# IMPORTANT: Run the server ONLY AFTER all routes are defined
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
