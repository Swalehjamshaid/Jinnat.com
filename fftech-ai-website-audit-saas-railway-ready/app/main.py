# app/main.py
# ... all your existing imports, middleware, other routes, etc. ...

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Import the new runner
from app.audit.runner import WebsiteAuditRunner

# Assuming you already have:
# app = FastAPI(...)
# templates = Jinja2Templates(directory="app/templates")
# manager = ConnectionManager()  # your WS manager
# ... other code ...

@app.post("/api/audit/run")
async def run_audit(payload: dict):
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    await manager.broadcast({"type": "progress", "message": "Starting audit...", "percent": 5})

    async def progress_callback(status: str, percent: int, payload: dict | None = None):
        await manager.broadcast({
            "type": "progress",
            "message": status,
            "percent": percent,
            "payload": payload
        })

    try:
        runner = WebsiteAuditRunner()
        result = await runner.run(url, progress_cb=progress_callback)

        await manager.broadcast({
            "type": "progress",
            "message": "Audit completed",
            "percent": 100,
            "result": result  # optional: send full result via WS too
        })

        return {
            "ok": True,
            "data": result,
            # You can also return whether SSL was relaxed if you add that info later
        }

    except Exception as exc:
        await manager.broadcast({
            "type": "error",
            "message": f"Audit failed: {str(exc)}"
        })
        raise HTTPException(status_code=500, detail=str(exc))


# The PORT fix we already discussed (keep this!)
if __name__ == "__main__":
    import uvicorn
    import os

    port_str = os.getenv("PORT")
    port = int(port_str) if port_str else 8000

    print(f"Starting server on 0.0.0.0:{port} (PORT from env: {port_str or 'not set'})")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
