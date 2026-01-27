import os
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

# --------------------------------------------------
# Logging
# --------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("FFTech_Main")

# --------------------------------------------------
# FastAPI App
# --------------------------------------------------
app = FastAPI(
    title="FF Tech AI Website Audit Engine",
    version="4.2.0",
)

# --------------------------------------------------
# Paths (Railway-safe)
# --------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
INDEX_FILE = os.path.join(BASE_DIR, "index.html")

os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --------------------------------------------------
# Index Route
# --------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if not os.path.exists(INDEX_FILE):
        logger.error("index.html missing")
        return HTMLResponse(
            "<h2>Deployment Error: index.html not found</h2>",
            status_code=500,
        )

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        return f.read()

# --------------------------------------------------
# WebSocket – Audit Progress
# --------------------------------------------------
@app.websocket("/ws/audit-progress")
async def websocket_audit(websocket: WebSocket):
    await websocket.accept()

    url = websocket.query_params.get("url")
    if not url:
        await websocket.send_json({
            "error": "URL is required",
            "finished": True,
        })
        await websocket.close()
        return

    logger.info(f"Audit started: {url}")

    try:
        # Import here to avoid Railway import issues
        from app.audit.runner import WebsiteAuditRunner

        runner = WebsiteAuditRunner(url)

        async def callback(payload: dict):
            """
            Safe callback used by WebsiteAuditRunner
            """
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                logger.warning("WebSocket runtime error during send")
            except Exception as e:
                logger.error(f"WebSocket send error: {e}")

        await runner.run_audit(callback)

    except WebSocketDisconnect:
        logger.info("Client disconnected")

    except Exception as e:
        logger.exception("Audit failed")
        try:
            await websocket.send_json({
                "error": str(e),
                "finished": True,
            })
        except Exception:
            pass

    finally:
        try:
            await websocket.close()
        except Exception:
            pass

        logger.info("WebSocket closed")

# --------------------------------------------------
# Local / Railway Entrypoint
# --------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Server starting on port {port}")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
