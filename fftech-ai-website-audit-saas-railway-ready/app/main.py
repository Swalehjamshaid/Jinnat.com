# -*- coding: utf-8 -*-
"""
app/main.py

FastAPI entrypoint
- WebSocket-powered website audit
- Streams progress + results from WebsiteAuditRunner
- Fully compatible with index.html dashboard & PDF export
"""

import asyncio
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.audit.runner import WebsiteAuditRunner

app = FastAPI(title="FF Tech Website Audit Engine")

# -----------------------------
# CORS (safe default)
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Health Check
# -----------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


# -----------------------------
# WebSocket Audit Endpoint
# -----------------------------
@app.websocket("/ws")
async def websocket_audit(ws: WebSocket):
    await ws.accept()

    try:
        # Receive initial payload
        payload = await ws.receive_json()
        url = payload.get("url", "").strip()

        if not url:
            await ws.send_json({
                "progress": 100,
                "status": "error",
                "error": "URL is required"
            })
            await ws.close()
            return

        runner = WebsiteAuditRunner()

        # --------------------------------
        # Progress callback → UI streaming
        # --------------------------------
        async def progress_cb(status: str, percent: int, data: Dict[str, Any] | None):
            msg = {
                "progress": percent,
                "status": status
            }
            if data is not None:
                msg["payload"] = data
            await ws.send_json(msg)

        # Run audit
        result = await runner.run(url, progress_cb=progress_cb)

        # Final payload (UI expects this)
        await ws.send_json({
            "progress": 100,
            "status": "completed",
            "result": result
        })

        await ws.close()

    except WebSocketDisconnect:
        print("WebSocket disconnected")

    except Exception as e:
        try:
            await ws.send_json({
                "progress": 100,
                "status": "error",
                "error": str(e)
            })
            await ws.close()
        except Exception:
            pass


# -----------------------------
# Optional: Simple UI test
# -----------------------------
@app.get("/")
async def index():
    return HTMLResponse("""
    <h2>FF Tech Website Audit API</h2>
    <p>WebSocket endpoint: <code>/ws</code></p>
    """)
