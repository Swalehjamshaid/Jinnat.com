# app/main.py
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.audit.runner import WebsiteAuditRunner
import os

app = FastAPI(title="FF Tech Audit Engine v4.3")

# Mount static folder if you have CSS/JS
if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")


# --------------------------
# Serve index.html
# --------------------------
@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


# --------------------------
# WebSocket: Live audit updates
# --------------------------
@app.websocket("/ws/audit-progress")
async def ws_audit_progress(websocket: WebSocket, url: str):
    await websocket.accept()
    try:
        async def callback(progress_data: dict):
            """
            This function is passed to WebsiteAuditRunner to send updates to the frontend.
            """
            await websocket.send_json(progress_data)

        audit_runner = WebsiteAuditRunner(url)
        await audit_runner.run_audit(callback)

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for {url}")
    except Exception as e:
        await websocket.send_json({"error": f"Server error: {str(e)}", "finished": True})
