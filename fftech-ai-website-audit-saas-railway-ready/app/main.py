import asyncio
import os
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

app = FastAPI()

# 1. FIX FOR STATIC FOLDER
# Automatically creates the folder if it's missing to prevent crashes
static_path = os.path.join(os.getcwd(), "static")
if not os.path.exists(static_path):
    os.makedirs(static_path, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    # 2. FIX FOR index.html NOT FOUND
    # Checks current folder AND parent folder for the HTML file
    paths_to_try = [
        "index.html",
        os.path.join(os.path.dirname(__file__), "..", "index.html"),
        os.path.join("app", "index.html")
    ]
    
    for path in paths_to_try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return f.read()
                
    return "<h1>Audit Engine</h1><p>Critical Error: index.html not found. Check project root.</p>"

@app.websocket("/ws/audit-progress")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    url = websocket.query_params.get("url")
    
    if not url:
        await websocket.send_json({"error": "No URL provided", "finished": True})
        await websocket.close()
        return

    try:
        # Import inside ensures Python path is ready
        from app.audit.runner import WebsiteAuditRunner
        runner = WebsiteAuditRunner(url)

        async def progress_callback(data: dict):
            try:
                await websocket.send_json(data)
            except Exception:
                pass 

        await runner.run_audit(progress_callback)

    except Exception as e:
        await websocket.send_json({"error": f"Backend Error: {str(e)}", "finished": True})
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
