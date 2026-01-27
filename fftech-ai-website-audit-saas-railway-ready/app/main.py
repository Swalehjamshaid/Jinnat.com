import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os

# Create the FastAPI app instance
app = FastAPI()

# Mount static files (ensure your 'static' folder exists for CSS/JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("index.html", "r") as f:
        return f.read()

@app.websocket("/ws/audit-progress")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    url = websocket.query_params.get("url")
    
    if not url:
        await websocket.send_json({"error": "No URL provided", "finished": True})
        await websocket.close()
        return

    try:
        # Import inside the endpoint to ensure the package structure is initialized
        from app.audit.runner import WebsiteAuditRunner
        
        runner = WebsiteAuditRunner(url)

        # Define the callback function to send JSON data through the WebSocket
        async def progress_callback(data: dict):
            try:
                await websocket.send_json(data)
            except Exception:
                pass  # Handle cases where client disconnects mid-audit

        # Run the audit with the provided callback
        await runner.run_audit(progress_callback)

    except ModuleNotFoundError as e:
        # Specifically catching the error seen in your logs
        await websocket.send_json({
            "error": f"Backend Configuration Error: {str(e)}. Ensure __init__.py exists in app/audit/",
            "finished": True
        })
    except Exception as e:
        await websocket.send_json({"error": f"System Error: {str(e)}", "finished": True})
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

if __name__ == "__main__":
    import uvicorn
    # Railway often uses the PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
