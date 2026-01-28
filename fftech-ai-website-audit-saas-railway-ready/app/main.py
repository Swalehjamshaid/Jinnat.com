# app/main.py
import asyncio
import json
import uuid
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.audit.runner import WebsiteAuditRunner

app = FastAPI(title="FF Tech Audit Engine v6")

# ──────────────────────────────────────────────
# CORS (safe default for SaaS)
# ──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# In-memory job store (Railway-safe)
# ──────────────────────────────────────────────
AUDIT_JOBS: Dict[str, Dict[str, Any]] = {}


# ──────────────────────────────────────────────
# Core audit executor
# ──────────────────────────────────────────────
async def run_audit_job(job_id: str, url: str):
    runner = WebsiteAuditRunner(url)

    async def callback(payload: Dict[str, Any]):
        AUDIT_JOBS[job_id]["last"] = payload
        AUDIT_JOBS[job_id]["history"].append(payload)

    try:
        await runner.run_audit(callback)
    except Exception as e:
        AUDIT_JOBS[job_id]["last"] = {
            "error": str(e),
            "finished": True
        }


# ──────────────────────────────────────────────
# WebSocket (PRIMARY – fastest UX)
# ──────────────────────────────────────────────
@app.websocket("/ws/audit-progress")
async def ws_audit_progress(ws: WebSocket, url: str):
    await ws.accept()

    try:
        runner = WebsiteAuditRunner(url)

        async def callback(payload: Dict[str, Any]):
            await ws.send_text(json.dumps(payload))
            if payload.get("finished"):
                await ws.close()

        await runner.run_audit(callback)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await ws.send_text(json.dumps({
            "error": f"WebSocket Error: {e}",
            "finished": True
        }))
        await ws.close()


# ──────────────────────────────────────────────
# SSE (SECONDARY fallback)
# ──────────────────────────────────────────────
@app.get("/sse/audit-progress")
async def sse_audit_progress(request: Request, url: str):
    job_id = str(uuid.uuid4())

    AUDIT_JOBS[job_id] = {
        "last": None,
        "history": []
    }

    asyncio.create_task(run_audit_job(job_id, url))

    async def event_stream():
        last_sent = None
        while True:
            if await request.is_disconnected():
                break

            payload = AUDIT_JOBS[job_id]["last"]
            if payload and payload != last_sent:
                yield f"data: {json.dumps(payload)}\n\n"
                last_sent = payload

                if payload.get("finished"):
                    break

            await asyncio.sleep(0.3)

    return app.responses.StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )


# ──────────────────────────────────────────────
# Polling (FINAL fallback)
# ──────────────────────────────────────────────
@app.get("/api/audit-start")
async def audit_start(url: str):
    job_id = str(uuid.uuid4())
    AUDIT_JOBS[job_id] = {
        "last": {"status": "⏳ Job queued", "crawl_progress": 0},
        "history": []
    }
    asyncio.create_task(run_audit_job(job_id, url))
    return {"job_id": job_id}


@app.get("/api/audit-poll")
async def audit_poll(job_id: str):
    job = AUDIT_JOBS.get(job_id)
    if not job:
        return JSONResponse(
            {"error": "Invalid job_id", "finished": True},
            status_code=404
        )
    return job["last"]


# ──────────────────────────────────────────────
# Health check (Railway / uptime)
# ──────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}
