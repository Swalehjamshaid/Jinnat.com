import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.audit.runner import WebsiteAuditRunner

app = FastAPI(title="FF Tech Audit Engine v4.3")

# ---------- Robust, file-relative paths ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")  # <-- index.html should be here
STATIC_DIR = os.path.join(BASE_DIR, "static")        # <-- optional assets (css/js/img)

# Mount /static if the folder exists (safe because NOT mounted at "/")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------- Health / debug ----------
@app.get("/health")
async def health_check():
    index_path = os.path.join(TEMPLATES_DIR, "index.html")
    return {
        "status": "online",
        "engine": "FF Tech v4.3",
        "templates_root": TEMPLATES_DIR,
        "index_exists": os.path.isfile(index_path),
        "static_root": STATIC_DIR,
        "static_exists": os.path.isdir(STATIC_DIR),
    }


# ---------- WebSocket route (kept as you had it) ----------
@app.websocket("/ws/audit-progress")
async def ws_audit_progress(websocket: WebSocket):
    await websocket.accept()

    # Extract the URL from query parameters: /ws/audit-progress?url=...
    url = websocket.query_params.get("url")

    if not url:
        await websocket.send_json({"error": "No URL provided", "finished": True})
        await websocket.close()
        return

    try:
        # Callback to push progress to the client
        async def callback(progress_data: dict):
            await websocket.send_json(progress_data)

        # Run the audit
        audit_runner = WebsiteAuditRunner(url)
        await audit_runner.run_audit(callback)

    except WebSocketDisconnect:
        print(f"ℹ️ User disconnected: {url}")
    except Exception as e:
        print(f"❌ Engine Error: {str(e)}")
        await websocket.send_json({"error": f"Internal Engine Error: {str(e)}", "finished": True})
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ---------- Serve the SPA at "/" ----------
@app.get("/")
async def serve_index():
    index_path = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    # If index.html is missing, signal clearly
    raise HTTPException(status_code=404, detail="index.html not found in app/templates")


# ---------- SPA fallback for client-side routes ----------
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str, request: Request):
    # Let API/WS/system paths 404 normally so they aren't hijacked by the SPA
    if full_path.startswith(("ws/", "api/", "openapi.json", "docs", "redoc", "health", "static/")):
        raise HTTPException(status_code=404, detail="Not found")

    # If a real file under /static is requested by a deep path, serve it
    requested_static = os.path.join(STATIC_DIR, full_path)
    if os.path.isfile(requested_static):
        return FileResponse(requested_static)

    # Otherwise, serve SPA index.html
    index_path = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)

    raise HTTPException(status_code=404, detail="index.html not found in app/templates")
