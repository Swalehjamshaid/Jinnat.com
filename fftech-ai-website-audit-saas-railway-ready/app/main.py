import os
import logging
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

# -------------------------------------------------
# Logging (Railway-friendly)
# -------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FFTech_Main")

# -------------------------------------------------
# App Init
# -------------------------------------------------
app = FastAPI(title="FFTech AI Website Audit")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Ensure static directory exists (prevents crash)
os.makedirs(STATIC_DIR, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# -------------------------------------------------
# Serve UI
# -------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = os.path.join(STATIC_DIR, "index.html")

    if not os.path.exists(index_path):
        logger.error("index.html missing")
        return HTMLResponse(
            content="""
            <h1>Deployment Error</h1>
            <p><strong>index.html not found</strong></p>
            <p>Expected location:</p>
            <pre>app/static/index.html</pre>
            """,
            status_code=500,
        )

    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

# -------------------------------------------------
# WebSocket: Audit Progress
# -------------------------------------------------
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

        async def progress_callback(payload: dict):
            try:
                await websocket.send_json(payload)
            except Exception:
                pass

        await runner.run_audit(progress_callback)

    except Exception as e:
        logger.exception("Audit failed")
        await websocket.send_json(
            {"error": f"Backend Error: {str(e)}", "finished": True}
        )

    finally:
        await websocket.close()

# -------------------------------------------------
# Local / Railway Startup
# -------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
