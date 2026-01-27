# app/main.py
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.audit.runner import WebsiteAuditRunner
import os

app = FastAPI(title="FF Tech Audit Engine v4.3")

# Serve static files (CSS/JS)
if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates folder
templates = Jinja2Templates(directory="templates")


# --------------------------
# Serve index.html from templates
# --------------------------
@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """
    Serve the main audit page.
    """
    return templates.TemplateResponse("index.html", {"request": request})


# --------------------------
# WebSocket: Live audit updates
# --------------------------
@app.websocket("/ws/audit-progress")
async def ws_audit_progress(websocket: WebSocket, url: str):
    """
    WebSocket endpoint that streams live audit progress to the frontend.
    """
    await websocket.accept()
    try:
        async def callback(progress_data: dict):
            """
            Callback passed to WebsiteAuditRunner to send JSON updates.
            """
            await websocket.send_json(progress_data)

        audit_runner = WebsiteAuditRunner(url)
        await audit_runner.run_audit(callback)

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for {url}")
    except Exception as e:
        await websocket.send_json({"error": f"Server error: {str(e)}", "finished": True})
