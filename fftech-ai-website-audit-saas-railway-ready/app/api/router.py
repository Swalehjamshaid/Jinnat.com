from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import logging
import tempfile

# ABSOLUTE IMPORTS
from app.db import get_db
from app.models import User, Audit
from app.schemas import AuditCreate, OpenAuditRequest, AuditOut
from app.audit.runner import run_audit
from app.audit.report import build_pdf
from app.auth.tokens import decode_token

router = APIRouter(prefix='/api', tags=['api'])

# Configure logger
logger = logging.getLogger("audit_api")


def get_current_user(request: Request, db: Session) -> User | None:
    """
    Get the current user from the session cookie.
    """
    token = request.cookies.get('session')
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    email = payload.get('sub')
    return db.query(User).filter(User.email == email).first()


@router.post('/open-audit')
async def open_audit(body: OpenAuditRequest, request: Request):
    """
    Open audit endpoint without rate limiting.
    Returns audit result JSON.
    """
    try:
        result = await run_audit(body.url)
        return result
    except Exception as e:
        logger.error(f"Open audit failed for URL {body.url}: {e}")
        raise HTTPException(status_code=500, detail="Failed to run audit")


@router.post('/audit', response_model=AuditOut)
async def create_audit(body: AuditCreate, request: Request, db: Session = Depends(get_db)):
    """
    Authenticated audit creation with DB save.
    Returns saved audit object.
    """
    user = get_current_user(request, db)
    if not user or not user.is_verified:
        raise HTTPException(401, 'Authentication required')

    try:
        # Run audit
        result = await run_audit(body.url)
    except Exception as e:
        logger.error(f"Audit run failed for user {user.email}, URL {body.url}: {e}")
        raise HTTPException(status_code=500, detail="Failed to run audit")

    try:
        # Save to DB
        audit = Audit(user_id=user.id, url=str(body.url), result_json=result)
        db.add(audit)
        user.audit_count += 1
        db.commit()
        db.refresh(audit)
    except Exception as e:
        logger.error(f"DB save failed for user {user.email}, URL {body.url}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save audit")

    return audit


@router.get('/audit/{audit_id}', response_model=AuditOut)
def get_audit(audit_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Get a saved audit by ID for the authenticated user.
    """
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(401, 'Authentication required')

    audit = db.query(Audit).filter(Audit.id == audit_id, Audit.user_id == user.id).first()
    if not audit:
        raise HTTPException(404, 'Audit not found')
    return audit


@router.get('/audit/{audit_id}/report.pdf')
def get_pdf(audit_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Generate PDF report for a specific audit.
    Returns PDF file.
    """
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(401, 'Authentication required')

    audit = db.query(Audit).filter(Audit.id == audit_id, Audit.user_id == user.id).first()
    if not audit:
        raise HTTPException(404, 'Audit not found')

    try:
        # Use a temporary file for PDF
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp_file.close()
        build_pdf(audit.result_json, tmp_file.name)
        return FileResponse(tmp_file.name, media_type='application/pdf', filename=f'audit_{audit_id}.pdf')
    except Exception as e:
        logger.error(f"PDF generation failed for audit {audit_id}: {e}")
        raise HTTPException(500, 'Failed to generate PDF')
