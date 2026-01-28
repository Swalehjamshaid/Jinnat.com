# main.py
import json
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.audit.runner import WebsiteAuditRunner

# --- FastAPI app
app = FastAPI(title="SEO Audit Runner", version="1.0")

# --- CORS (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Static (optional): if you store assets like /static/app.css, /static/logo.svg
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# --- Serve index.html
@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = Path("index.html")
    if index_path.exists():
        return FileResponse(str(index_path))
    # fallback
    return HTMLResponse("<h2>index.html not found</h2>", status_code=404)

# --- WebSocket for streaming audit
@app.websocket("/ws/audit")
async def ws_audit(ws: WebSocket):
    await ws.accept()
    try:
        # Expect a JSON message like: {"url": "www.haier.com.pk"}
        init_msg = await ws.receive_text()
        data = json.loads(init_msg)
        url = (data.get("url") or "").strip()
        if not url:
            await ws.send_json({"error": "No URL provided", "finished": True})
            await ws.close()
            return

        runner = WebsiteAuditRunner(url)

        async def callback(message: Dict[str, Any]):
            # Stream runner messages to the client
            try:
                await ws.send_json(message)
            except WebSocketDisconnect:
                # Client gone; stop streaming silently
                pass

        await runner.run_audit(callback)
        await ws.close()

    except WebSocketDisconnect:
        # Client disconnected mid-run
        return
    except Exception as e:
        try:
            await ws.send_json({"error": f"Server Error: {str(e)}", "finished": True})
        except Exception:
            pass
        try:
            await ws.close()
        except Exception:
            pass

# --- Local dev entrypoint:
# uvicorn main:app --reload --host 0.0.0.0 --port 8000
