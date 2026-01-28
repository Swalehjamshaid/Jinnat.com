# main.py
import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import the flexible runner you updated
from app.audit.runner import WebsiteAuditRunner

# -----------------------------------------------------------------------------
# App Initialization
# -----------------------------------------------------------------------------
app = FastAPI(title="Audit Service", version="1.0.0")

# CORS – liberal defaults; tighten for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # consider restricting to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
logger = logging.getLogger("audit")
logging.basicConfig(level=logging.INFO)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
async def _stream_to_websocket(ws: WebSocket, message: Dict[str, Any]) -> None:
    """Send JSON-safe message to WebSocket with robust error handling."""
    try:
        await ws.send_text(json.dumps(message, ensure_ascii=False, default=str))
    except Exception as e:
        # Fail silently to avoid crashing the runner; the WebSocket may have closed
        logger.warning("WebSocket send failed: %s", e)


def _normalize_url(url: Optional[str]) -> str:
    if not url or not isinstance(url, str):
        raise HTTPException(status_code=422, detail="`url` is required and must be a string.")
    return url if url.startswith("http") else f"https://{url}"


# -----------------------------------------------------------------------------
# WebSocket: live streaming endpoint
# -----------------------------------------------------------------------------
@app.websocket("/ws/audit")
async def ws_audit(ws: WebSocket):
    """
    WebSocket endpoint that streams progress messages AND the final audit payload.
    Client must send a JSON message: {"url": "<domain or url>"}
    """
    await ws.accept()
    try:
        init_msg = await ws.receive_text()
        try:
            payload = json.loads(init_msg)
        except Exception:
            await _stream_to_websocket(ws, {"error": "Invalid JSON. Send: {\"url\": \"example.com\"}"})
            await ws.close()
            return

        url = _normalize_url(payload.get("url"))
        runner = WebsiteAuditRunner(url)

        # Callback used by the runner to stream incremental updates
        async def ws_callback(msg: Dict[str, Any]):
            await _stream_to_websocket(ws, msg)

        await runner.run_audit(ws_callback)

        # Ensure we close gracefully after the run
        await ws.close(code=1000)

    except WebSocketDisconnect:
        logger.info("Client disconnected WebSocket.")
    except Exception as e:
        logger.exception("WebSocket error: %s", e)
        try:
            await _stream_to_websocket(ws, {"error": f"Server error: {str(e)}", "finished": True})
            await ws.close(code=1011)
        except Exception:
            pass


# -----------------------------------------------------------------------------
# HTTP: one-shot audit (final JSON only)
# -----------------------------------------------------------------------------
@app.post("/audit")
async def http_audit(request: Request):
    """
    HTTP endpoint that runs the audit and returns ONLY the final payload.
    Body JSON: {"url": "www.example.com"}
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    url = _normalize_url(body.get("url"))
    runner = WebsiteAuditRunner(url)

    # Capture the final message emitted by the runner
    final_payload: Dict[str, Any] = {}

    # We still need to supply a callback; for HTTP we ignore progress events
    async def http_callback(msg: Dict[str, Any]):
        # Save the last payload containing finished=True or error
        nonlocal final_payload
        if msg.get("finished") or msg.get("error"):
            final_payload = msg

    await runner.run_audit(http_callback)

    if not final_payload:
        # Safety fallback – this should not happen, but prevents empty responses
        raise HTTPException(status_code=500, detail="No payload produced by the audit.")

    # In case of error from runner, return 500 with the message
    if "error" in final_payload:
        return JSONResponse(status_code=500, content=final_payload)

    return JSONResponse(status_code=200, content=final_payload)


# -----------------------------------------------------------------------------
# Health & Root
# -----------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {
        "service": "Audit Service",
        "version": "1.0.0",
        "endpoints": {
            "http": "POST /audit  (body: {\"url\": \"www.example.com\"})",
            "websocket": "WS /ws/audit  (send: {\"url\": \"www.example.com\"})",
            "health": "GET /health",
        },
    }


# -----------------------------------------------------------------------------
# Local Dev Entrypoint (optional)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # This block is optional; keep if you run `python main.py` in dev.
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
