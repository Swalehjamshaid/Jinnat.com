import os
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

app = FastAPI()

# This finds the exact folder where this script is running
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Fix: Ensure static directory exists to prevent backend crashes
static_path = os.path.join(BASE_DIR, "static")
os.makedirs(static_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    # Fix: This looks for index.html in the SAME folder as main.py
    index_path = os.path.join(BASE_DIR, "index.html")
    
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    
    # Precise error reporting for Railway logs
    return f"<h1>Critical Error</h1><p>File not found at: {index_path}</p>"

@app.websocket("/ws/audit-progress")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    url = websocket.query_params.get("url")
    
    if not url:
        await websocket.send_json({"error": "No URL provided", "finished": True})
        return

    try:
        # Import inside ensures Python finds your 'app' folder correctly
        from app.audit.runner import WebsiteAuditRunner
        runner = WebsiteAuditRunner(url)

        async def progress_callback(data: dict):
            try:
                await websocket.send_json(data)
            except:
                pass 

        await runner.run_audit(progress_callback)

    except Exception as e:
        # This sends the error to the UI so the loading bar disappears
        await websocket.send_json({"error": f"Backend Error: {str(e)}", "finished": True})
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    # Railway dynamic port mapping
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
