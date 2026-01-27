import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.audit.runner import WebsiteAuditRunner

app = FastAPI(title="FF Tech Audit Engine v4.3")

# 1. ROBUST PATH DETECTION
# This ensures the engine finds the "static" folder regardless of where it's deployed
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)
    print(f"⚠️ Warning: {STATIC_DIR} was missing. Created it.")

# 2. DEBUG / STATUS ENDPOINT
@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "engine": "FF Tech v4.3",
        "static_root": STATIC_DIR,
        "index_exists": os.path.isfile(os.path.join(STATIC_DIR, "index.html"))
    }

# 3. WEBSOCKET ROUTE (Must be defined BEFORE the static mount)
@app.websocket("/ws/audit-progress")
async def ws_audit_progress(websocket: WebSocket):
    await websocket.accept()
    
    # Extract the URL from query parameters: /ws/audit-progress?url=...
    url = websocket.query_params.get("url")
    
    if not url:
        await websocket.send_json({"error": "No URL provided", "finished": True})
        await websocket.close()
        return

    try:
        # This callback function allows the runner to talk back to the browser
        async def callback(progress_data: dict):
            await websocket.send_json(progress_data)

        # Initialize and run the audit logic
        audit_runner = WebsiteAuditRunner(url)
        await audit_runner.run_audit(callback)
        
    except WebSocketDisconnect:
        print(f"ℹ️ User disconnected: {url}")
    except Exception as e:
        print(f"❌ Engine Error: {str(e)}")
        await websocket.send_json({"error": f"Internal Engine Error: {str(e)}", "finished": True})
    finally:
        try:
            await websocket.close()
        except:
            pass

# 4. STATIC FILES MOUNT (The Catch-All)
# This MUST be last. It handles "/" by serving index.html automatically.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
