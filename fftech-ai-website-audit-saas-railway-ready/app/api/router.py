# app/api/router.py

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import time
import os
import logging

from app.db import get_db
from app.models import User, Audit
from app.schemas import AuditCreate, OpenAuditRequest, AuditOut
from app.audit.grader import run_audit
from app.services.pdf_generator import generate_full_audit_pdf
from app.auth.tokens import decode_token

router = APIRouter(prefix="/api", tags=["api"])
logger = logging.getLogger(__name__)


def get_current_user(request: Request, db: Session):
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
    FULL ASYNC AUDIT – FIXED
    """
    url_string = str(body.url)

    # 🔥 THIS WAS THE CRASH — NOW FIXED
    audit_result = await run_audit(url_string)

    return audit_result


@router.get("/download-full-audit")
async def download_report(url: str = Query(...)):
    url_string = str(url)

    report_data = await run_audit(url_string)

    os.makedirs("reports", exist_ok=True)
    file_path = f"reports/Audit_{int(time.time())}.pdf"

    generate_full_audit_pdf(report_data, file_path)

    return FileResponse(
        path=file_path,
        filename="FFTech_Certified_Audit.pdf",
        media_type="application/pdf",
    )


@router.post("/audit", response_model=AuditOut)
async def create_audit(
    body: AuditCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    url_string = str(body.url)

    result = await run_audit(url_string)

    audit = Audit(
        user_id=user.id,
        url=url_string,
        result_json=result,
    )

    db.add(audit)
    user.audit_count += 1
    db.commit()
    db.refresh(audit)

    return audit
