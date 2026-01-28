import os
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.audit.runner import WebsiteAuditRunner

app = FastAPI(title="FF Tech Audit Engine v4.3")

# ---------- Robust, file-relative paths (unchanged externally) ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")  # <— index.html here
STATIC_DIR = os.path.join(BASE_DIR, "static")        # <— optional (css/js/img)

# Only mount /static if folder exists (keeps behavior intact)
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------- Health / debug (unchanged route and response keys) ----------
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


# ---------- WebSocket route (kept EXACT path and query contract) ----------
@app.websocket("/ws/audit-progress")
async def ws_audit_progress(websocket: WebSocket):
    await websocket.accept()

    # Extract the URL from query parameters: /ws/audit-progress?url=...
    url = websocket.query_params.get("url")

    if not url:
        await _safe_ws_send(websocket, {"error": "No URL provided", "finished": True})
        await _safe_ws_close(websocket)
        return

    try:
        # The callback is unchanged — it forwards each runner message directly
        async def callback(progress_data: Dict[str, Any]):
            # NOTE: This preserves your existing streaming protocol and payload shape.
            await _safe_ws_send(websocket, progress_data)

        # Run the audit (the new runner adapts to future analyzer changes automatically)
        audit_runner = WebsiteAuditRunner(url)
        await audit_runner.run_audit(callback)

    except WebSocketDisconnect:
        # Non-fatal: user closed the socket
        print(f"ℹ️ User disconnected: {url}")

    except Exception as e:
        # Preserve your error envelope
        print(f"❌ Engine Error: {str(e)}")
        await _safe_ws_send(websocket, {"error": f"Internal Engine Error: {str(e)}", "finished": True})

    finally:
        await _safe_ws_close(websocket)


# ---------- Serve the SPA at "/" (same behavior) ----------
@app.get("/")
async def serve_index():
    index_path = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found in app/templates")


# ---------- SPA fallback for client-side routes (same paths preserved) ----------
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str, request: Request):
    # Keep API/WS/system routes as hard 404s (unchanged logic)
    if full_path.startswith(("ws/", "api/", "openapi.json", "docs", "redoc", "health", "static/")):
        raise HTTPException(status_code=404, detail="Not found")

    # Serve a real static asset if requested
    requested_static = os.path.join(STATIC_DIR, full_path)
    if os.path.isfile(requested_static):
        return FileResponse(requested_static)

    # Otherwise return SPA index
    index_path = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)

    raise HTTPException(status_code=404, detail="index.html not found in app/templates")


# ---------- Internal WS helpers (do not change external contract) ----------
async def _safe_ws_send(websocket: WebSocket, data: Dict[str, Any]):
    """
    Sends JSON over WS safely. If the client disconnects mid-send,
    we swallow the exception to avoid breaking the server loop.
    """
    try:
        await websocket.send_json(data)
    except RuntimeError:
        # Socket closed while sending — ignore gracefully
        pass
    except Exception as e:
        # Log but do not alter the outward contract
        print(f"WS send error: {e}")

async def _safe_ws_close(websocket: WebSocket):
    """
    Closes the WS if still open; errors are ignored to keep behavior stable.
    """
    try:
        await websocket.close()
    except Exception:
        pass
``
