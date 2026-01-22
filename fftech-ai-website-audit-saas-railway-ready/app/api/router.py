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

router = APIRouter(prefix='/api', tags=['api'])

logger = logging.getLogger("app.api.router")

def get_current_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get("session")
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    email = payload.get("sub")
    return db.query(User).filter(User.email == email).first()


@router.post("/open-audit")
async def open_audit(body: OpenAuditRequest, request: Request):
    """Triggers the 200-metric audit suite."""
    from app.settings import get_settings
    settings = get_settings()

    ip = (request.client.host if request and request.client else "anon")
    key = f"{ip}:{int(time.time()) // 3600}"

    if not hasattr(open_audit, "RATE_TRACK"):
        open_audit.RATE_TRACK = {}
    count = open_audit.RATE_TRACK.get(key, 0)

    if count >= settings.RATE_LIMIT_OPEN_PER_HOUR:
        raise HTTPException(429, "Rate limit exceeded.")

    open_audit.RATE_TRACK[key] = count + 1

    # Convert Pydantic HttpUrl object to string to prevent 'unhashable' error
    url_string = str(body.url)

    # Run audit safely, return structured default if audit fails
    try:
        result = run_audit(url_string)
        if result is None:
            result = {"url": url_string, "overall_score": 0, "grade": "N/A", "categories": {}}
    except Exception as e:
        logger.error(f"Audit failed for URL {url_string}: {e}")
        result = {"url": url_string, "overall_score": 0, "grade": "N/A", "categories": {}}

    return result


@router.get("/download-full-audit")
async def download_report(url: str = Query(...)):
    """Metric 10: Certified Export Readiness."""
    url_string = str(url)

    try:
        report_data = run_audit(url_string)
        if report_data is None:
            report_data = {"url": url_string, "overall_score": 0, "grade": "N/A", "categories": {}}
    except Exception as e:
        logger.error(f"Audit failed for download URL {url_string}: {e}")
        report_data = {"url": url_string, "overall_score": 0, "grade": "N/A", "categories": {}}

    # Ensure reports folder exists
    os.makedirs("reports", exist_ok=True)
    file_path = f"reports/Audit_{int(time.time())}.pdf"

    try:
        generate_full_audit_pdf(report_data, file_path)
    except Exception as e:
        logger.error(f"PDF generation failed for {url_string}: {e}")
        raise HTTPException(500, "Failed to generate audit PDF.")

    return FileResponse(path=file_path, filename="FFTech_Certified_Audit.pdf")


@router.post("/audit", response_model=AuditOut)
def create_audit(body: AuditCreate, request: Request, db: Session = Depends(get_db)):
    """Store audit in database for authenticated users."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(401, "Authentication required")

    url_string = str(body.url)

    try:
        result = run_audit(url_string)
        if result is None:
            result = {"url": url_string, "overall_score": 0, "grade": "N/A", "categories": {}}
    except Exception as e:
        logger.error(f"Audit failed for DB storage URL {url_string}: {e}")
        result = {"url": url_string, "overall_score": 0, "grade": "N/A", "categories": {}}

    audit = Audit(user_id=user.id, url=url_string, result_json=result)
    db.add(audit)
    user.audit_count += 1
    db.commit()
    db.refresh(audit)
    return audit
