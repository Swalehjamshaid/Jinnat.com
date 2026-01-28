# app/main.py
import os
import json
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.audit.runner import WebsiteAuditRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit")

app = FastAPI(title="SEO Audit – Flexible Runner")


# -------------------------------------------------
# Static files (index.html)
# -------------------------------------------------
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """
    Serve the fixed index.html
    """
    index_path = os.path.join(STATIC_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()


# -------------------------------------------------
# WebSocket: /ws/audit
# -------------------------------------------------
@app.websocket("/ws/audit")
async def audit_ws(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected")

    try:
        # Wait for initial message { url: "..." }
        raw = await websocket.receive_text()
        payload = json.loads(raw)
        url = payload.get("url")

        if not url:
            await websocket.send_json({
                "error": "No URL provided",
                "finished": True
            })
            return

        runner = WebsiteAuditRunner(url)

        # Callback used by runner to stream updates
        async def ws_callback(message: dict):
            try:
                await websocket.send_json(message)
            except RuntimeError:
                # socket already closed
                pass

        # Run audit
        await runner.run_audit(ws_callback)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")

    except Exception as e:
        logger.exception("WebSocket audit failed")
        try:
            await websocket.send_json({
                "error": f"Server error: {e}",
                "finished": True
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# -------------------------------------------------
# Health (optional, but useful)
# -------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


# -------------------------------------------------
# Entrypoint
# -------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
