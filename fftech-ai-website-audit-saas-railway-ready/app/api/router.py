from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

# Absolute imports from the app package
from app.db import get_db
from app.models import User, Audit
from app.schemas import AuditCreate, OpenAuditRequest, AuditOut
from app.audit.crawler import analyze
from app.audit.report import build_pdf
from app.auth.tokens import decode_token

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
    from app.settings import get_settings
    settings = get_settings()
    
    # Rate limiting logic
    ip = (request.client.host if request and request.client else 'anon')
    import time
    now = int(time.time())
    window = now // 3600
    key = f"{ip}:{window}"
    
    if not hasattr(open_audit, 'RATE_TRACK'):
        open_audit.RATE_TRACK = {}
    count = open_audit.RATE_TRACK.get(key, 0)
    
    if count >= settings.RATE_LIMIT_OPEN_PER_HOUR:
        raise HTTPException(429, 'Rate limit exceeded for open audits. Please try later or sign in.')
    
    open_audit.RATE_TRACK[key] = count + 1
    
    # Calls the analyze function inside crawler.py
    return await analyze(body.url)

@router.post('/audit', response_model=AuditOut)
async def create_audit(body: AuditCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or not user.is_verified:
        raise HTTPException(401, 'Authentication required')
    
    from app.settings import get_settings
    settings = get_settings()
    
    if user.plan == 'free' and user.audit_count >= settings.FREE_AUDIT_LIMIT:
        raise HTTPException(403, f'Free plan limit reached ({settings.FREE_AUDIT_LIMIT} audits)')
    
    # Analyze using the crawler module
    result = await analyze(body.url)
    
    audit = Audit(
        user_id=user.id,
        url=str(body.url),
        result_json=result,
        overall_score=result.get('overall_score', 0),
        grade=result.get('grade', 'F')
    )
    db.add(audit)
    user.audit_count += 1
    db.commit()
    db.refresh(audit)
    return audit

@router.get('/audit/{audit_id}/report.pdf')
def get_pdf(audit_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(401, 'Authentication required')
        
    audit = db.query(Audit).filter(Audit.id == audit_id, Audit.user_id == user.id).first()
    if not audit:
        raise HTTPException(404, 'Not found')
    
    # Ensure directory exists for Railway
    import os
    os.makedirs("storage/reports", exist_ok=True)
    
    out_path = f"storage/reports/audit_{audit_id}.pdf"
    
    # Build the PDF
    build_pdf(
        audit.id,
        audit.url,
        audit.overall_score,
        audit.grade,
        audit.result_json.get('category_scores'),
        audit.result_json.get('metrics'),
        "storage/reports"
    )
    
    return FileResponse(out_path, media_type='application/pdf', filename=f'FF_Tech_Report_{audit_id}.pdf')
