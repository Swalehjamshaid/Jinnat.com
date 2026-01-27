import os
import logging
from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FFTech_Main")

app = FastAPI(title="FFTech AI Website Audit")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Create if needed (harmless)
os.makedirs(STATIC_DIR, exist_ok=True)

# Mount everything at root (/, /static/js/..., /index.html directly works too)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        logger.error("index.html missing in static/")
        return HTMLResponse(
            "<h1>Deployment Error</h1><p>index.html missing in static/</p>",
            status_code=500
        )
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()


# Fallback for client-side paths (future-proof if you add router-based JS)
@app.get("/{path:path}", response_class=HTMLResponse, include_in_schema=False)
async def catch_all(request: Request, path: str):
    # Skip websocket & api-like paths
    if path.startswith("ws/") or path in ["openapi.json", "docs", "redoc"]:
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))  # or raise 404

    full_path = os.path.join(STATIC_DIR, path)
    if os.path.isfile(full_path):
        return FileResponse(full_path)

    # SPA fallback
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    
    return HTMLResponse("<h1>404 Not Found</h1>", status_code=404)


@app.websocket("/ws/audit-progress")
async def audit_progress(websocket: WebSocket):
    await websocket.accept()
    url = websocket.query_params.get("url")
    if not url:
        await websocket.send_json({"error": "URL not provided", "finished": True})
        await websocket.close()
        return

    try:
        from app.audit.runner import WebsiteAuditRunner
        runner = WebsiteAuditRunner(url)

        async def progress_callback(data: dict):
            await websocket.send_json(data)

        await runner.run_audit(progress_callback)
    except Exception as e:
        logger.exception("Audit failed")
        await websocket.send_json({"error": str(e), "finished": True})
    finally:
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
