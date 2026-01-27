import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

app = FastAPI()

# --- FIX FOR RUNTIME ERROR: Directory 'static' does not exist ---
# We check if the folder exists before mounting to prevent the container from crashing
static_path = os.path.join(os.getcwd(), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory="static"), name="static")
else:
    # Create the directory automatically if it's missing to avoid future errors
    os.makedirs(static_path, exist_ok=True)
    app.mount("/static", StaticFiles(directory="static"), name="static")
    print("Created missing 'static' directory.")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    # Ensure index.html is in the root directory
    try:
        with open("index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Audit Engine</h1><p>index.html not found in root.</p>"

@app.websocket("/ws/audit-progress")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    url = websocket.query_params.get("url")
    
    if not url:
        await websocket.send_json({"error": "No URL provided", "finished": True})
        await websocket.close()
        return

    try:
        # --- FIX FOR ModuleNotFoundError: No module named 'app.audit.link' ---
        # Import inside the endpoint ensures the app package is fully initialized
        from app.audit.runner import WebsiteAuditRunner
        
        runner = WebsiteAuditRunner(url)

        async def progress_callback(data: dict):
            try:
                # Send real-time updates to the UI
                await websocket.send_json(data)
            except Exception:
                pass 

        # Execute the refined audit logic
        await runner.run_audit(progress_callback)

    except Exception as e:
        # Send the exact error to the UI so it doesn't stay 'stuck'
        await websocket.send_json({"error": f"Backend Error: {str(e)}", "finished": True})
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

if __name__ == "__main__":
    import uvicorn
    # Railway dynamic port assignment
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
