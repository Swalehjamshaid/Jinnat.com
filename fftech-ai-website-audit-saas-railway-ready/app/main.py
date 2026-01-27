import os
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

app = FastAPI()

# This line finds the EXACT folder where main.py is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. FIX: Automatically handle the static folder to prevent crashes
static_path = os.path.join(BASE_DIR, "static")
if not os.path.exists(static_path):
    os.makedirs(static_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    # 2. FIX: Look for index.html in the same folder as main.py
    index_path = os.path.join(BASE_DIR, "index.html")
    
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    
    # This error message helps us debug if it's still missing
    return f"<h1>Critical Error</h1><p>File not found at: {index_path}</p>"

@app.websocket("/ws/audit-progress")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    url = websocket.query_params.get("url")
    
    try:
        # 3. FIX: Ensure sub-modules are imported correctly
        from app.audit.runner import WebsiteAuditRunner
        runner = WebsiteAuditRunner(url)

        async def progress_callback(data: dict):
            try:
                await websocket.send_json(data)
            except:
                pass 

        await runner.run_audit(progress_callback)

    except Exception as e:
        await websocket.send_json({"error": f"Backend Error: {str(e)}", "finished": True})
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
