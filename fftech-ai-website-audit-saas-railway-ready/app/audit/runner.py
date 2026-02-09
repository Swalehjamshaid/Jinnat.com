# app/main.py
# -*- coding: utf-8 -*-

import os
import asyncio
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.audit.runner import WebsiteAuditRunner

# -----------------------------
# App setup
# -----------------------------
app = FastAPI(title="FF Tech Website Audit SaaS")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

runner = WebsiteAuditRunner()

# -----------------------------
# WebSocket Manager
# -----------------------------
class WSManager:
    def __init__(self):
        self.connections = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.add(ws)

    def disconnect(self, ws: WebSocket):
        self.connections.discard(ws)

    async def send(self, msg: dict):
        for ws in list(self.connections):
            try:
                await ws.send_json(msg)
            except Exception:
                self.disconnect(ws)

ws_manager = WSManager()

# -----------------------------
# Routes
# -----------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)

@app.post("/api/audit")
async def audit_site(payload: dict):
    url = payload.get("url", "").strip()
    if not url:
        return JSONResponse({"error": "URL is required"}, status_code=400)

    async def progress_cb(status, percent, payload=None):
        await ws_manager.send({
            "type": "progress",
            "status": status,
            "percent": percent,
            "payload": payload,
        })

    result = await runner.run(url, progress_cb=progress_cb)
    return result

# -----------------------------
# Entry point (PORT FIX)
# -----------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
