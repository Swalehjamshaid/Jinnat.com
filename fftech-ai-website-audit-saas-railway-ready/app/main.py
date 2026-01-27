import os
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

app = FastAPI()

# This calculates the absolute path to the root folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Fix: Ensure static directory exists to prevent Starlette RuntimeError
static_path = os.path.join(BASE_DIR, "static")
os.makedirs(static_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    # Fix: Search for index.html in the same directory as this script
    index_path = os.path.join(BASE_DIR, "index.html")
    
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    
    # Error reporting to help us debug Railway paths
    return f"<h1>Critical Error</h1><p>File not found at: {index_path}</p>"

@app.websocket("/ws/audit-progress")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    url = websocket.query_params.get("url")
    
    if not url:
        await websocket.send_json({"error": "No URL provided", "finished": True})
        await websocket.close()
        return

    try:
        # Import inside ensures the 'app' package is found by Python
        from app.audit.runner import WebsiteAuditRunner
        runner = WebsiteAuditRunner(url)

        async def progress_callback(data: dict):
            try:
                await websocket.send_json(data)
            except:
                pass 

        await runner.run_audit(progress_callback)

    except Exception as e:
        # Prevents the "Initializing Engine" bar from staying stuck forever
        await websocket.send_json({"error": f"Backend Error: {str(e)}", "finished": True})
    finally:
        try:
            await websocket.close()
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    # Railway dynamic port mapping
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
