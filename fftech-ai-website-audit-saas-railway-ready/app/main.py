from fastapi import FastAPI, WebSocket, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.audit.runner import WebsiteAuditRunner
import json
import asyncio

app = FastAPI()

# Assuming your index.html is in a folder named 'templates'
@app.get("/")
async def get():
    with open("templates/index.html") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws/audit-progress")
async def websocket_endpoint(websocket: WebSocket, url: str = Query(...)):
    await websocket.accept()
    
    # Callback to send updates back to the frontend
    async def progress_callback(data: dict):
        await websocket.send_text(json.dumps(data))

    runner = WebsiteAuditRunner(url)
    try:
        await runner.run_audit(progress_callback)
    except Exception as e:
        await websocket.send_text(json.dumps({"error": str(e), "finished": True}))
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
