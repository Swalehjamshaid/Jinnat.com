import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.audit.runner import WebsiteAuditRunner

app = FastAPI(title="FF Tech Audit Engine v4.3")

# Ensure static folder exists (runtime safety)
STATIC_DIR = "static"
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# Mount static files at root → serves index.html automatically for "/"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

# Optional explicit root route (extra safety + debug message if file missing)
@app.get("/", include_in_schema=False)
async def serve_root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        return {"error": "index.html not found in /static folder"}
    return FileResponse(index_path)

# Debug endpoint – helps confirm file presence after deploy
@app.get("/debug-static")
async def debug_static():
    index_path = os.path.join(STATIC_DIR, "index.html")
    return {
        "static_dir_exists": os.path.isdir(STATIC_DIR),
        "index_file_exists": os.path.isfile(index_path),
        "current_working_dir": os.getcwd(),
        "note": "Visit / to see the dashboard"
    }

# ────────────────────────────────────────────────
# WebSocket: Live audit updates (unchanged)
# ────────────────────────────────────────────────
@app.websocket("/ws/audit-progress")
async def ws_audit_progress(websocket: WebSocket):
    await websocket.accept()
    url = websocket.query_params.get("url")
    if not url:
        await websocket.send_json({"error": "URL not provided", "finished": True})
        await websocket.close()
        return

    try:
        async def callback(progress_data: dict):
            await websocket.send_json(progress_data)

        audit_runner = WebsiteAuditRunner(url)
        await audit_runner.run_audit(callback)
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for {url}")
    except Exception as e:
        await websocket.send_json({"error": f"Server error: {str(e)}", "finished": True})
    finally:
        await websocket.close()
