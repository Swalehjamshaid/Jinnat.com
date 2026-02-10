# app/main.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Request,
    HTTPException
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.runner import run_audit  # your existing audit logic

# -------------------------------------------------
# App setup
# -------------------------------------------------
app = FastAPI(title="Client Website Audit Report")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

# -------------------------------------------------
# Recommendation Engine (RULE-BASED = SELLABLE)
# -------------------------------------------------
def generate_recommendations(scores: Dict[str, int]) -> list[str]:
    recs = []

    if scores.get("performance", 100) < 60:
        recs.append(
            "Improve performance by compressing images, reducing unused JavaScript, and enabling browser caching."
        )

    if scores.get("seo", 100) < 70:
        recs.append(
            "Improve SEO by fixing meta descriptions, heading structure (H1–H3), and adding alt text to images."
        )

    if scores.get("accessibility", 100) < 70:
        recs.append(
            "Improve accessibility by increasing color contrast, adding ARIA labels, and fixing missing form labels."
        )

    if scores.get("security", 100) < 80:
        recs.append(
            "Improve security by enforcing HTTPS redirects, enabling HSTS, and updating outdated libraries."
        )

    if not recs:
        recs.append("The website is performing well. Maintain current best practices.")

    return recs

# -------------------------------------------------
# Core audit handler
# -------------------------------------------------
async def process_audit(payload: Dict[str, Any], progress_cb=None) -> Dict[str, Any]:
    url = payload["url"]

    if progress_cb:
        await progress_cb("Starting website audit…")

    audit_result = await run_audit(url, progress_cb)

    scores = audit_result.get("scores", {})

    final_report = {
        "meta": {
            "client_name": payload.get("client_name", "N/A"),
            "brand_name": payload.get("brand_name", "N/A"),
            "website_name": payload.get("website_name", url),
            "report_title": payload.get("report_title", "Website Audit Report"),
            "generated_at": datetime.utcnow().isoformat()
        },
        "url": url,
        "scores": scores,
        "details": audit_result.get("details", {}),
        "recommendations": generate_recommendations(scores)
    }

    # Save report for history / PDF
    filename = f"{REPORTS_DIR}/audit_{int(datetime.utcnow().timestamp())}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2)

    if progress_cb:
        await progress_cb("Audit completed successfully")

    return final_report

# -------------------------------------------------
# REST endpoint (fallback / API usage)
# -------------------------------------------------
@app.post("/audit")
async def audit_api(request: Request):
    payload = await request.json()

    if "url" not in payload:
        raise HTTPException(status_code=400, detail="URL is required")

    report = await process_audit(payload)
    return JSONResponse(report)

# -------------------------------------------------
# WebSocket endpoint (LIVE PROGRESS = PREMIUM FEEL)
# -------------------------------------------------
@app.websocket("/ws/audit")
async def audit_ws(websocket: WebSocket):
    await websocket.accept()

    try:
        payload = await websocket.receive_json()

        async def progress(msg: str):
            await websocket.send_json({"type": "progress", "message": msg})

        report = await process_audit(payload, progress)

        await websocket.send_json({
            "type": "result",
            "data": report
        })

    except WebSocketDisconnect:
        print("WebSocket disconnected")

    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })

# -------------------------------------------------
# Health check
# -------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}
