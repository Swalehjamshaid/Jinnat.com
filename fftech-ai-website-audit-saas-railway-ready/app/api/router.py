
# app/api/router.py

from __future__ import annotations

import os
import time
import uuid
import logging
import asyncio
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, Audit
from app.schemas import AuditCreate, OpenAuditRequest, AuditOut
from app.audit.grader import run_audit, AuditError, PSIRequestError
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


def _normalize_and_validate_url(url: str) -> str:
    """
    Ensure URL has scheme and is parseable. PSI needs a valid, public URL.
    Raises HTTPException 400 for invalid input.
    """
    if not isinstance(url, str) or not url.strip():
        raise HTTPException(status_code=400, detail="URL is required")

    url = url.strip()

    # Auto-prepend https:// if missing (optional but user-friendly)
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL. Include a valid domain with http(s) scheme.")
    return url


def _compact_psi_detail(e: PSIRequestError) -> dict:
    """
    Provide a compact, user-friendly detail payload for PSI 400 errors.
    """
    body = getattr(e, "body", {}) or {}
    # Extract common fields from PSI error payload if present
    err = body.get("error", {}) if isinstance(body, dict) else {}
    message = err.get("message") or str(e)
    reason = (err.get("errors") or [{}])[0].get("reason")
    return {"message": message, "reason": reason, "psi_body": body}


@router.post("/open-audit")
async def open_audit(body: OpenAuditRequest):
    """
    Run a full async Google PSI audit (mobile + desktop) and return JSON.
    - Validates URL before calling PSI (prevents many 400s).
    - Maps PSI 400 to HTTP 400 with body details; other PSI errors to 502.
    """
    url_string = _normalize_and_validate_url(str(body.url or ""))
    try:
        result = await run_audit(url_string, locale=getattr(body, "locale", None))
        return result
    except PSIRequestError as e:
        # PSI 400 → return 400 with PSI body so client can act
        if getattr(e, "status", None) == 400:
            detail = _compact_psi_detail(e)
            logger.warning("PSI 400 for %s: %s", url_string, detail)
            raise HTTPException(status_code=400, detail=detail) from e
        # Other PSI errors (429/5xx/timeouts after retries) → 502
        logger.exception("PSI error for %s", url_string)
        raise HTTPException(status_code=502, detail=str(e)) from e
    except AuditError as e:
        logger.exception("Audit module error for %s", url_string)
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        logger.exception("Unhandled error during /open-audit for %s", url_string)
        raise HTTPException(status_code=500, detail="Internal Server Error") from e


@router.get("/download-full-audit")
async def download_report(url: str = Query(..., description="Website URL to audit")):
    """
    Runs the audit, generates a full PDF report, and returns it as a file download.
    - Audit call is awaited (async).
    - PDF generation is offloaded to a thread (non-blocking for event loop).
    - PSI 400 is surfaced to client as 400 with details.
    """
    url_string = _normalize_and_validate_url(url)
    try:
        report_data = await run_audit(url_string)

        os.makedirs("reports", exist_ok=True)
        unique = uuid.uuid4().hex
        file_path = os.path.join("reports", f"Audit_{int(time.time())}_{unique}.pdf")

        # Offload sync PDF generation to a worker thread
        await asyncio.to_thread(generate_full_audit_pdf, report_data, file_path)

        return FileResponse(
            path=file_path,
            filename="FFTech_Certified_Audit.pdf",
            media_type="application/pdf",
        )
    except PSIRequestError as e:
        if getattr(e, "status", None) == 400:
            detail = _compact_psi_detail(e)
            logger.warning("PSI 400 during PDF for %s: %s", url_string, detail)
            raise HTTPException(status_code=400, detail=detail) from e
        logger.exception("PSI error during PDF for %s", url_string)
        raise HTTPException(status_code=502, detail=str(e)) from e
    except AuditError as e:
        logger.exception("Audit module error during PDF for %s", url_string)
        raise HTTPException(status_code=502, detail=str(e)) from e
    except FileNotFoundError:
        logger.exception("PDF generation failed: file not found for %s", url_string)
        raise HTTPException(status_code=500, detail="Report generation failed")
    except Exception:
        logger.exception("Unhandled error during /download-full-audit for %s", url_string)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/audit", response_model=AuditOut)
async def create_audit(
    body: AuditCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Authenticated endpoint: runs an audit, persists it, increments user's audit_count,
    and returns the saved row.
    - PSI 400 is returned as 400 to the client.
    """
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    url_string = _normalize_and_validate_url(str(body.url or ""))

    try:
        result = await run_audit(url_string)

        audit = Audit(
            user_id=user.id,
            url=url_string,
            result_json=result,  # ensure JSON/JSONB column type
        )

        db.add(audit)
        user.audit_count = (user.audit_count or 0) + 1
        db.commit()
        db.refresh(audit)

        return audit
    except PSIRequestError as e:
        if getattr(e, "status", None) == 400:
            detail = _compact_psi_detail(e)
            logger.warning("PSI 400 during /audit for %s: %s", url_string, detail)
            raise HTTPException(status_code=400, detail=detail) from e
        logger.exception("PSI error during /audit for %s", url_string)
        raise HTTPException(status_code=502, detail=str(e)) from e
    except AuditError as e:
        logger.exception("Audit module error during /audit for %s", url_string)
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception:
        db.rollback()
        logger.exception("Unhandled error during /audit for %s", url_string)
        raise HTTPException(status_code=500, detail="Internal Server Error")
``
