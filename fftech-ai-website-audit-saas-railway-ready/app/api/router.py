
# app/api/router.py

from __future__ import annotations

import os
import time
import uuid
import logging
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, Audit
from app.schemas import AuditCreate, OpenAuditRequest, AuditOut
from app.audit.grader import run_audit, AuditError
from app.services.pdf_generator import generate_full_audit_pdf
from app.auth.tokens import decode_token

router = APIRouter(prefix="/api", tags=["api"])
logger = logging.getLogger(__name__)


def get_current_user(request: Request, db: Session) -> Optional[User]:
    """
    Returns the current user inferred from the 'session' cookie JWT.
    If not present/invalid, returns None (caller decides how to handle).
    """
    token = request.cookies.get("session")
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    return db.query(User).filter(User.email == payload.get("sub")).first()


@router.post("/open-audit")
async def open_audit(body: OpenAuditRequest):
    """
    Run a full async Google PSI audit (mobile + desktop) and return JSON.
    Ensures the result is awaited and JSON-serializable to avoid FastAPI
    serialization errors like `'coroutine' object is not iterable`.
    """
    url_string = str(body.url or "").strip()
    if not url_string:
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        # ✅ Await the async audit (prevents returning a coroutine)
        audit_result = await run_audit(url_string, locale=getattr(body, "locale", None))
        return audit_result
    except AuditError as e:
        # Known audit error (network, PSI, parse) → 502 Bad Gateway
        logger.exception("AuditError during /open-audit for %s", url_string)
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        # Unknown error → 500
        logger.exception("Unhandled error during /open-audit for %s", url_string)
        raise HTTPException(status_code=500, detail="Internal Server Error") from e


@router.get("/download-full-audit")
async def download_report(url: str = Query(..., description="Website URL to audit")):
    """
    Runs the audit, generates a full PDF report, and returns it as a file download.
    - The audit call is awaited (async).
    - PDF generation (likely CPU/IO-bound and synchronous) is offloaded to a thread
      so the event loop remains responsive.
    """
    url_string = str(url or "").strip()
    if not url_string:
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        # 1) Run the async audit
        report_data = await run_audit(url_string)

        # 2) Ensure reports directory exists
        os.makedirs("reports", exist_ok=True)

        # 3) Build a unique filename to avoid collisions
        unique = uuid.uuid4().hex
        file_path = os.path.join("reports", f"Audit_{int(time.time())}_{unique}.pdf")

        # 4) Offload synchronous PDF generation to a worker thread
        await asyncio.to_thread(generate_full_audit_pdf, report_data, file_path)

        # 5) Return the PDF file
        return FileResponse(
            path=file_path,
            filename="FFTech_Certified_Audit.pdf",
            media_type="application/pdf",
        )
    except AuditError as e:
        logger.exception("AuditError during /download-full-audit for %s", url_string)
        raise HTTPException(status_code=502, detail=str(e)) from e
    except FileNotFoundError as e:
        logger.exception("PDF generation failed: file not found for %s", url_string)
        raise HTTPException(status_code=500, detail="Report generation failed") from e
    except Exception as e:
        logger.exception("Unhandled error during /download-full-audit for %s", url_string)
        raise HTTPException(status_code=500, detail="Internal Server Error") from e


@router.post("/audit", response_model=AuditOut)
async def create_audit(
    body: AuditCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Authenticated endpoint that runs an audit, stores the result in DB,
    increments user's audit_count, and returns the stored audit row.

    IMPORTANT:
    - `run_audit` is awaited to avoid returning coroutines.
    - SQLAlchemy session work is synchronous; FastAPI runs sync dependencies
      in a threadpool, so this is safe here.
    """
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    url_string = str(body.url or "").strip()
    if not url_string:
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        # Run the async audit
        result = await run_audit(url_string)

        # Persist audit
        audit = Audit(
            user_id=user.id,
            url=url_string,
            result_json=result,  # ensure this column is JSON/JSONB compatible
        )

        db.add(audit)
        # Keep audit count accurate
        user.audit_count = (user.audit_count or 0) + 1
        db.commit()
        db.refresh(audit)

        return audit
    except AuditError as e:
        logger.exception("AuditError during /audit for %s", url_string)
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        # Rollback DB on unexpected errors
        logger.exception("Unhandled error during /audit for %s", url_string)
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error") from e
