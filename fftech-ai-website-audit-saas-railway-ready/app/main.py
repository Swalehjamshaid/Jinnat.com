import os
import json
from fastapi import FastAPI, WebSocket, Query
from fastapi.responses import HTMLResponse

app = FastAPI()

# Crucial: Fixes the FileNotFoundError for Railway
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/")
async def get():
    template_path = os.path.join(BASE_DIR, "templates", "index.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws/audit-progress")
async def websocket_endpoint(websocket: WebSocket, url: str = Query(...)):
    await websocket.accept()
    
    # Import inside the function to avoid circular import issues
    from app.audit.runner import WebsiteAuditRunner
    
    async def progress_callback(data: dict):
        await websocket.send_text(json.dumps(data))

    runner = WebsiteAuditRunner(url)
    await runner.run_audit(progress_callback)
