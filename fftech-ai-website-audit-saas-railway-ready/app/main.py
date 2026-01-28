# main.py
import asyncio
import json
import logging
from typing import Any, Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import the flexible runner
from app.audit.runner import WebsiteAuditRunner

# -----------------------------------------------------------------------------
# App Initialization
# -----------------------------------------------------------------------------
app = FastAPI(title="FF Tech Audit Engine", version="1.0.0")

# CORS – very permissive for development & Railway proxy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production: ["https://your-frontend-domain.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging – visible in Railway logs
logger = logging.getLogger("audit-service")
logging.basicConfig(level=logging.INFO)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
async def _send_json(ws: WebSocket, message: Dict[str, Any]) -> None:
    """Safe JSON send with error handling"""
    try:
        await ws.send_text(json.dumps(message, ensure_ascii=False, default=str))
    except Exception as e:
        logger.warning("WebSocket send failed: %s", e)


def _normalize_url(url: Optional[str]) -> str:
    if not url or not isinstance(url, str):
        raise ValueError("`url` is required and must be a string.")
    return url if url.startswith(("http://", "https://")) else f"https://{url}"

# -----------------------------------------------------------------------------
# WebSocket Endpoint – Matches frontend's /ws/audit
# -----------------------------------------------------------------------------
@app.websocket("/ws/audit")
async def websocket_audit(websocket: WebSocket):
    """
    WebSocket endpoint that:
    - Waits for first message: {"url": "https://example.com"}
    - Runs full audit with progress streaming
    - Sends final payload when finished
    """
    await websocket.accept()

    try:
        # Receive initial message from frontend
        init_msg = await websocket.receive_text()
        try:
            payload = json.loads(init_msg)
            url = _normalize_url(payload.get("url"))
        except Exception as e:
            await _send_json(websocket, {"error": f"Invalid message: {str(e)}. Send: {{'url': 'example.com'}}"})
            await websocket.close(code=1008)  # Policy violation
            return

        logger.info(f"WebSocket audit started for URL: {url}")

        # Initial progress
        await _send_json(websocket, {
            "status": "🚀 Audit engine starting...",
            "crawl_progress": 5
        })

        # Run the audit with streaming callback
        runner = WebsiteAuditRunner(url)

        async def ws_callback(msg: Dict[str, Any]):
            # Add timestamp for debugging
            msg["timestamp"] = time.time()
            await _send_json(websocket, msg)

        await runner.run_audit(ws_callback)

        # Final message (in case runner doesn't send finished)
        await _send_json(websocket, {
            "status": "Audit complete",
            "finished": True
        })

        await websocket.close(code=1000)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")

    except Exception as e:
        logger.exception("WebSocket error: %s", e)
        try:
            await _send_json(websocket, {
                "error": f"Server error: {str(e)}",
                "finished": True
            })
            await websocket.close(code=1011)  # Internal error
        except Exception:
            pass

# -----------------------------------------------------------------------------
# HTTP Endpoint – one-shot final result (alternative to WS)
# -----------------------------------------------------------------------------
@app.post("/audit")
async def http_audit(request: Request):
    """
    POST /audit with JSON body: {"url": "https://example.com"}
    Returns only the final payload (no streaming)
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON body. Send {\"url\": \"...\"}")

    url = body.get("url")
    if not url:
        raise HTTPException(422, detail="`url` field is required")

    normalized_url = _normalize_url(url)

    runner = WebsiteAuditRunner(normalized_url)
    final_payload: Dict[str, Any] = {}

    async def http_callback(msg: Dict[str, Any]):
        nonlocal final_payload
        if msg.get("finished") or msg.get("error"):
            final_payload = msg

    await runner.run_audit(http_callback)

    if not final_payload:
        raise HTTPException(500, detail="No audit result produced")

    if "error" in final_payload:
        return JSONResponse(status_code=500, content=final_payload)

    return JSONResponse(status_code=200, content=final_payload)

# -----------------------------------------------------------------------------
# Health & Info Endpoints
# -----------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "FF Tech Audit Engine"}

@app.get("/")
async def root():
    return {
        "service": "FF Tech Audit Engine API",
        "version": "1.0.0",
        "websocket": "wss://your-domain/ws/audit (send {\"url\": \"https://example.com\"})",
        "http": "POST /audit with JSON body {\"url\": \"https://example.com\"}",
        "health": "GET /health"
    }

# -----------------------------------------------------------------------------
# Local Development (optional)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
