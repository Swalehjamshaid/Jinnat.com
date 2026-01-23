from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

# ABSOLUTE IMPORTS
from app.db import get_db
from app.models import User, Audit, Schedule
from app.schemas import AuditCreate, OpenAuditRequest, AuditOut
from app.audit.runner import run_audit
from app.audit.report import build_pdf
from app.auth.tokens import decode_token
from app.settings import get_settings

router = APIRouter(prefix='/api', tags=['api'])

def get_current_user(request: Request, db: Session) -> User | None:
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
    Open audit endpoint with Rate Limiting disabled.
    """
    # Rate limit logic removed to prevent '429 Too Many Requests'
    
    # run_audit is an async function in app/audit/runner.py
    return await run_audit(body.url)

@router.post('/audit', response_model=AuditOut)
async def create_audit(body: AuditCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or not user.is_verified:
        raise HTTPException(401, 'Authentication required')
    
    # Audit logic
    result = await run_audit(body.url)
    
    # Save to DB
    audit = Audit(user_id=user.id, url=str(body.url), result_json=result)
    db.add(audit)
    user.audit_count += 1
    db.commit()
    db.refresh(audit)
    return audit

@router.get('/audit/{audit_id}', response_model=AuditOut)
def get_audit(audit_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(401, 'Authentication required')
    
    audit = db.query(Audit).filter(Audit.id == audit_id, Audit.user_id == user.id).first()
    if not audit:
        raise HTTPException(404, 'Not found')
    return audit

@router.get('/audit/{audit_id}/report.pdf')
def get_pdf(audit_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(401, 'Authentication required')
    
    audit = db.query(Audit).filter(Audit.id == audit_id, Audit.user_id == user.id).first()
    if not audit:
        raise HTTPException(404, 'Not found')
    
    out_path = f"/tmp/audit_{audit_id}.pdf"
    build_pdf(audit.result_json, out_path)
    return FileResponse(out_path, media_type='application/pdf', filename=f'audit_{audit_id}.pdf')
