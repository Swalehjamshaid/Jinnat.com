# app/main.py
import os
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.audit.runner import WebsiteAuditRunner

# ---------------------------
# Paths & Templates
# ---------------------------
APP_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = APP_DIR / "templates"
INDEX_PATH = TEMPLATES_DIR / "index.html"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ---------------------------
# FastAPI App
# ---------------------------
app = FastAPI(title="Flexible Audit Runner", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Utility Functions
# ---------------------------
def _validate_url(url: str | None) -> str:
    if not url or not isinstance(url, str) or len(url.strip()) < 4:
        raise HTTPException(status_code=400, detail="Provide a valid URL")
    url = url.strip()
    return url if url.startswith("http") else f"https://{url}"

async def _run_audit_queue(url: str, queue: asyncio.Queue):
    """Run the audit and push messages to an asyncio queue"""
    runner = WebsiteAuditRunner(url)

    async def callback(msg: Dict[str, Any]):
        """Send messages to queue for streaming"""
        try:
            json.dumps(msg)  # ensure serializable
            await queue.put(msg)
        except Exception:
            await queue.put({"error": "Non-serializable message", "finished": True})

    await runner.run_audit(callback)

async def _sse_stream(queue: asyncio.Queue) -> AsyncGenerator[bytes, None]:
    """Server-Sent Event stream"""
    HEARTBEAT = 10
    while True:
        try:
            msg = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT)
            yield f"data: {json.dumps(msg)}\n\n".encode("utf-8")
            if msg.get("finished") or msg.get("error"):
                break
        except asyncio.TimeoutError:
            yield b": heartbeat\n\n"

# ---------------------------
# Routes
# ---------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if INDEX_PATH.exists():
        return templates.TemplateResponse("index.html", {"request": request})
    return HTMLResponse("<h1>Index not found</h1>", status_code=404)

@app.get("/healthz")
async def healthz():
    return {"ok": True, "app": "audit-runner"}

@app.get("/api/audit")
async def audit_sse(url: str | None = None):
    """SSE endpoint for streaming audit updates"""
    target = _validate_url(url)
    queue: asyncio.Queue = asyncio.Queue()
    asyncio.create_task(_run_audit_queue(target, queue))
    return StreamingResponse(_sse_stream(queue), media_type="text/event-stream")

@app.post("/api/audit", response_class=JSONResponse)
async def audit_once(request: Request):
    """Single-run audit returning final JSON"""
    body = await request.json()
    target = _validate_url(body.get("url"))
    final_payload: Dict[str, Any] = {}
    done = asyncio.Event()

    async def callback(msg: Dict[str, Any]):
        nonlocal final_payload
        final_payload = msg
        if msg.get("finished") or msg.get("error"):
            done.set()

    runner = WebsiteAuditRunner(target)
    task = asyncio.create_task(runner.run_audit(callback))
    try:
        await asyncio.wait_for(done.wait(), timeout=float(os.getenv("AUDIT_TIMEOUT", "120")))
    except asyncio.TimeoutError:
        task.cancel()
        raise HTTPException(status_code=504, detail="Audit timed out")
    return JSONResponse(final_payload or {"error": "No payload"})

# ---------------------------
# WebSocket Endpoint
# ---------------------------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        init_data = await ws.receive_text()
        try:
            data = json.loads(init_data)
        except Exception:
            await ws.send_text(json.dumps({"error": "Send JSON like {\"url\": \"https://example.com\"}"}))
            await ws.close()
            return

        url = _validate_url(data.get("url"))

        async def callback(msg: Dict[str, Any]):
            await ws.send_text(json.dumps(msg, ensure_ascii=False))

        runner = WebsiteAuditRunner(url)
        await runner.run_audit(callback)
        await ws.close()
    except WebSocketDisconnect:
        return
    except Exception as e:
        await ws.send_text(json.dumps({"error": f"Server error: {e}", "finished": True}))
        await ws.close()

# ---------------------------
# Run Uvicorn
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=bool(os.getenv("RELOAD", "1") == "1"))
