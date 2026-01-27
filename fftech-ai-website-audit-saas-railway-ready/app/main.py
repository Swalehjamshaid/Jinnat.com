import os
from fastapi import FastAPI, WebSocket, Query
from fastapi.responses import HTMLResponse
import json

app = FastAPI()

# FIX: Define the absolute base directory to prevent FileNotFoundError
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/")
async def get():
    # Use BASE_DIR to reliably find the templates folder
    template_path = os.path.join(BASE_DIR, "templates", "index.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="Error: index.html not found.", status_code=404)

@app.websocket("/ws/audit-progress")
async def websocket_endpoint(websocket: WebSocket, url: str = Query(...)):
    await websocket.accept()
    
    # Import the runner inside the endpoint to ensure clean starts
    from app.audit.runner import WebsiteAuditRunner
    
    async def progress_callback(data: dict):
        await websocket.send_text(json.dumps(data))

    runner = WebsiteAuditRunner(url)
    try:
        # The audit runs here. Ensure your runner has timeouts for external APIs!
        await runner.run_audit(progress_callback)
    except Exception as e:
        await websocket.send_text(json.dumps({"error": str(e), "finished": True}))
    finally:
        await websocket.close()
