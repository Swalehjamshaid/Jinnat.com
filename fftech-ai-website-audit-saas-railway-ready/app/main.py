import os
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

app = FastAPI()

# Locate the root directory for file serving
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure the 'static' folder exists and mount it
static_path = os.path.join(BASE_DIR, "static")
os.makedirs(static_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serves the refined Audit Engine HTML interface."""
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Critical Error</h1><p>index.html was not found in the root directory.</p>"

@app.websocket("/ws/audit-progress")
async def websocket_endpoint(websocket: WebSocket):
    """Handles real-time audit streaming to the frontend."""
    await websocket.accept()
    url = websocket.query_params.get("url")
    
    if not url:
        await websocket.send_json({"error": "No URL provided", "finished": True})
        await websocket.close()
        return

    try:
        # Internal imports ensure the 'app' module is ready
        from app.audit.runner import WebsiteAuditRunner
        runner = WebsiteAuditRunner(url)

        async def progress_callback(data: dict):
            try:
                # Sends real-time updates (status messages, progress bar %)
                await websocket.send_json(data)
            except Exception:
                pass 

        # Execute the full audit logic
        await runner.run_audit(progress_callback)

    except Exception as e:
        # Sends errors back to the UI so the loading bar doesn't stay stuck
        await websocket.send_json({"error": f"Backend Error: {str(e)}", "finished": True})
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

if __name__ == "__main__":
    import uvicorn
    # Railway uses the PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
