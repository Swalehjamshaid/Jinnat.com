# app/main.py
import os
import json
import asyncio
import contextlib
from pathlib import Path
from typing import Any, Dict, Optional, AsyncGenerator, Callable

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
    allow_origins=["*"],  # keep as-is
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------
# URL Validation (same input contract)
# ---------------------------
def _validate_url(url: Optional[str]) -> str:
    if not url or not isinstance(url, str) or len(url.strip()) < 4:
        raise HTTPException(status_code=400, detail="Provide a valid URL")
    u = url.strip()
    return u if u.startswith("http") else f"https://{u}"


# ---------------------------
# JSON Safe Dump (never crashes)
# ---------------------------
def _json_dumps_safe(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        # fallback: stringify non-serializable values
        try:
            return json.dumps({"error": "Non-serializable message", "raw": str(obj)}, ensure_ascii=False)
        except Exception:
            return '{"error":"Non-serializable message"}'


# ---------------------------
# Flexible Runner Adapter
# Supports BOTH:
# 1) WebsiteAuditRunner().run(url, progress_cb=...)
# 2) WebsiteAuditRunner(url).run_audit(callback)
# ---------------------------
async def _run_runner_flexible(
    target_url: str,
    push: Callable[[Dict[str, Any]], Any],
    timeout_s: float,
) -> None:
    """
    Streams progress messages to push(...) and finishes with a completed/final message.
    Does NOT change your endpoints or input formats.
    """

    async def progress_emit(status: str, percent: int, payload: Optional[dict] = None) -> None:
        msg: Dict[str, Any] = {"status": status, "progress": int(percent)}
        if payload:
            # If payload looks like final result, we embed it as result (for UI)
            if isinstance(payload, dict) and (
                "overall_score" in payload or "breakdown" in payload or "grade" in payload
            ):
                msg["result"] = payload
            else:
                msg.update(payload)
        await push(msg)

    # Try "new style" runner first: WebsiteAuditRunner().run(url, progress_cb=...)
    try:
        runner = WebsiteAuditRunner()  # new-style runner has no required init args

        if hasattr(runner, "run") and callable(getattr(runner, "run")):
            # start
            await progress_emit("starting", 5, {"url": target_url})

            async def cb(status: str, percent: int, payload: Optional[dict] = None):
                await progress_emit(status, percent, payload)

            # run with timeout
            try:
                result = await asyncio.wait_for(runner.run(target_url, progress_cb=cb), timeout=timeout_s)
            except asyncio.TimeoutError:
                await push({"error": "Audit timed out", "finished": True})
                return

            # final message (keep finished contract)
            await push({
                "status": "completed",
                "progress": 100,
                "result": result,
                "finished": True
            })
            return
    except TypeError:
        # runner likely requires (url) in constructor => old style
        pass
    except Exception as e:
        # runner init/logic error
        await push({"error": f"Runner error: {e}", "finished": True})
        return

    # Old style runner: WebsiteAuditRunner(url).run_audit(callback)
    try:
        runner = WebsiteAuditRunner(target_url)

        if not hasattr(runner, "run_audit") or not callable(getattr(runner, "run_audit")):
            await push({"error": "Runner interface not supported", "finished": True})
            return

        async def old_callback(msg: Dict[str, Any]):
            # Pass-through message, but ensure it won’t crash JSON encoding
            if not isinstance(msg, dict):
                msg = {"message": str(msg)}
            await push(msg)

        try:
            await asyncio.wait_for(runner.run_audit(old_callback), timeout=timeout_s)
        except asyncio.TimeoutError:
            await push({"error": "Audit timed out", "finished": True})
            return

        # If old runner didn’t emit finished, ensure we do
        await push({"status": "completed", "progress": 100, "finished": True})
        return

    except Exception as e:
        await push({"error": f"Runner error: {e}", "finished": True})
        return


# ---------------------------
# SSE Streaming Generator
# ---------------------------
async def _sse_stream(queue: asyncio.Queue) -> AsyncGenerator[bytes, None]:
    HEARTBEAT = 10
    while True:
        try:
            msg = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT)
            yield f"data: {_json_dumps_safe(msg)}\n\n".encode("utf-8")
            if isinstance(msg, dict) and (msg.get("finished") or msg.get("error")):
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
async def audit_sse(url: Optional[str] = None):
    """
    SSE endpoint streaming audit updates
    Input stays same: /api/audit?url=example.com
    """
    target = _validate_url(url)
    queue: asyncio.Queue = asyncio.Queue()

    timeout_s = float(os.getenv("AUDIT_TIMEOUT", "120"))

    async def push(msg: Dict[str, Any]):
        await queue.put(msg)

    task = asyncio.create_task(_run_runner_flexible(target, push=push, timeout_s=timeout_s))

    async def stream_wrapper():
        try:
            async for chunk in _sse_stream(queue):
                yield chunk
        finally:
            task.cancel()
            with contextlib.suppress(Exception):
                await task

    return StreamingResponse(stream_wrapper(), media_type="text/event-stream")


@app.post("/api/audit", response_class=JSONResponse)
async def audit_once(request: Request):
    """
    Single-run audit returning final JSON
    Input stays same: {"url":"example.com"}
    """
    body = await request.json()
    target = _validate_url(body.get("url"))

    timeout_s = float(os.getenv("AUDIT_TIMEOUT", "120"))
    final_payload: Dict[str, Any] = {}
    done = asyncio.Event()

    async def push(msg: Dict[str, Any]):
        nonlocal final_payload
        # Prefer final result when present
        if isinstance(msg, dict) and "result" in msg and isinstance(msg["result"], dict):
            final_payload = msg["result"]
        else:
            final_payload = msg

        if isinstance(msg, dict) and (msg.get("finished") or msg.get("error")):
            done.set()

    task = asyncio.create_task(_run_runner_flexible(target, push=push, timeout_s=timeout_s))
    try:
        await asyncio.wait_for(done.wait(), timeout=timeout_s + 5)
    except asyncio.TimeoutError:
        task.cancel()
        raise HTTPException(status_code=504, detail="Audit timed out")
    finally:
        task.cancel()
        with contextlib.suppress(Exception):
            await task

    return JSONResponse(final_payload or {"error": "No payload"})


# ---------------------------
# WebSocket Endpoint (same /ws)
# ---------------------------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()

    timeout_s = float(os.getenv("AUDIT_TIMEOUT", "120"))

    async def ws_push(msg: Dict[str, Any]):
        # send safe JSON
        await ws.send_text(_json_dumps_safe(msg))

    try:
        init_data = await ws.receive_text()

        try:
            data = json.loads(init_data)
        except Exception:
            await ws_push({"error": "Send JSON like {\"url\": \"https://example.com\"}", "finished": True})
            await ws.close()
            return

        url = _validate_url(data.get("url"))

        await _run_runner_flexible(url, push=ws_push, timeout_s=timeout_s)

        with contextlib.suppress(Exception):
            await ws.close()

    except WebSocketDisconnect:
        return
    except Exception as e:
        with contextlib.suppress(Exception):
            await ws_push({"error": f"Server error: {e}", "finished": True})
            await ws.close()


# ---------------------------
# Run Uvicorn (local dev)
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
