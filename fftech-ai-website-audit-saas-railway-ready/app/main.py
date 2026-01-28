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

# -----------------------------------------------------------------------------
# Paths – updated to point to app/templates/index.html
# -----------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = APP_DIR / "templates"
INDEX_PATH = TEMPLATES_DIR / "index.html"

# Initialize Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# -----------------------------------------------------------------------------
# FastAPI app with permissive CORS (tune for production)
# -----------------------------------------------------------------------------
app = FastAPI(title="Flexible Audit Runner", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------
def _ok_url(url: str | None) -> str:
    if not url or not isinstance(url, str) or len(url.strip()) < 4:
        raise HTTPException(status_code=400, detail="Provide a valid ?url= parameter or JSON body with {'url': '...'}")
    u = url.strip()
    return u if u.startswith("http") else f"https://{u}"

async def _runner_to_queue(url: str, queue: asyncio.Queue):
    """Run the audit and push callback messages into an asyncio.Queue."""
    runner = WebsiteAuditRunner(url)
    async def cb(msg: Dict[str, Any]):
        try:
            json.dumps(msg)
            await queue.put(msg)
        except Exception:
            await queue.put({"error": "Non-serializable message encountered", "finished": True})
    await runner.run_audit(cb)

async def _sse_stream(queue: asyncio.Queue) -> AsyncGenerator[bytes, None]:
    """
    Server-Sent Events stream. Yields `data: <json>\n\n`.
    Includes heartbeat comments to keep proxies/load balancers happy.
    """
    HEARTBEAT_EVERY = 10  # seconds
    last_sent = asyncio.get_event_loop().time()
    while True:
        try:
            msg = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_EVERY)
            payload = json.dumps(msg, ensure_ascii=False)
            yield f"data: {payload}\n\n".encode("utf-8")
            last_sent = asyncio.get_event_loop().time()
            if msg.get("finished") or msg.get("error"):
                break
        except asyncio.TimeoutError:
            now = asyncio.get_event_loop().time()
            if now - last_sent >= HEARTBEAT_EVERY:
                yield b": heartbeat\n\n"
                last_sent = now

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Serves app/templates/index.html at root URL.
    Shows friendly error if file is missing.
    """
    if INDEX_PATH.exists():
        return templates.TemplateResponse("index.html", {"request": request})
    
    # Fallback if index.html is not found
    return HTMLResponse(
        content="""
        <h1 style="color: #ef4444; text-align: center; margin-top: 100px;">
            Index file not found
        </h1>
        <p style="text-align: center; font-family: monospace;">
            Please make sure index.html exists at:<br>
            <strong>app/templates/index.html</strong>
        </p>
        """,
        status_code=200
    )

@app.get("/healthz")
async def healthz():
    return {"ok": True, "app": "audit-runner", "version": "1.0.0"}

@app.get("/api/audit")
async def audit_sse(url: str | None = None):
    """
    **SSE endpoint**: GET /api/audit?url=https://example.com
    Streams multiple messages; the final one contains the full payload.
    """
    target = _ok_url(url)
    q: asyncio.Queue = asyncio.Queue()
    asyncio.create_task(_runner_to_queue(target, q))
    return StreamingResponse(_sse_stream(q), media_type="text/event-stream")

@app.post("/api/audit", response_class=JSONResponse)
async def audit_once(request: Request):
    """
    **One-shot JSON endpoint**: POST /api/audit
    Body: {"url": "https://example.com"}
    Returns only the final payload (no streaming).
    """
    body = await request.json()
    target = _ok_url(body.get("url"))
    final_payload: Dict[str, Any] = {}
    done = asyncio.Event()

    async def cb(msg: Dict[str, Any]):
        nonlocal final_payload
        final_payload = msg
        if msg.get("finished") or msg.get("error"):
            done.set()

    runner = WebsiteAuditRunner(target)
    task = asyncio.create_task(runner.run_audit(cb))

    try:
        await asyncio.wait_for(done.wait(), timeout=float(os.getenv("AUDIT_TIMEOUT", "120")))
    except asyncio.TimeoutError:
        task.cancel()
        raise HTTPException(status_code=504, detail="Audit timed out.")

    return JSONResponse(final_payload or {"error": "No payload"})

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """
    **WebSocket endpoint**:
    1) Client connects to /ws
    2) Sends: {"url": "https://example.com"}
    3) Receives multiple JSON messages; final contains finished=true
    """
    await ws.accept()
    try:
        init = await ws.receive_text()
        try:
            data = json.loads(init)
        except Exception:
            await ws.send_text(json.dumps({"error": "Send a JSON like {\"url\": \"https://example.com\"}"}))
            await ws.close()
            return
        url = _ok_url(data.get("url"))
        async def cb(msg: Dict[str, Any]):
            await ws.send_text(json.dumps(msg, ensure_ascii=False))
        runner = WebsiteAuditRunner(url)
        await runner.run_audit(cb)
        await ws.close()
    except WebSocketDisconnect:
        # Client disconnected; nothing else to do
        return
    except Exception as e:
        await ws.send_text(json.dumps({"error": f"Server error: {e}", "finished": True}))
        await ws.close()

# -----------------------------------------------------------------------------
# Local dev entrypoint: uvicorn app.main:app --reload --port 8000
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=bool(os.getenv("RELOAD", "1") == "1"))
