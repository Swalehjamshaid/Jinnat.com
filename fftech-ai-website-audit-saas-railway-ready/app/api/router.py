from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import time

# Absolute imports for stability in Railway/Docker
from app.db import get_db
from app.models import User, Audit, Schedule
from app.schemas import AuditCreate, OpenAuditRequest, AuditOut
from app.audit.grader import run_audit  
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
    """
    Handles the 'Audit' button click from the landing page.
    """
    from app.settings import get_settings
    settings = get_settings()
    
    # Basic Rate Limiting
    ip = (request.client.host if request and request.client else 'anon')
    now = int(time.time())
    window = now // 3600
    key = f"{ip}:{window}"
    
    if not hasattr(open_audit, 'RATE_TRACK'):
        open_audit.RATE_TRACK = {}
    
    count = open_audit.RATE_TRACK.get(key, 0)
    if count >= settings.RATE_LIMIT_OPEN_PER_HOUR:
        raise HTTPException(429, 'Rate limit exceeded. Please sign in.')
    
    open_audit.RATE_TRACK[key] = count + 1
    
    # This triggers the grader logic
    return run_audit(body.url)

@router.post('/audit', response_model=AuditOut)
def create_audit(body: AuditCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or not user.is_verified:
        raise HTTPException(401, 'Authentication required')
    
    result = run_audit(body.url)
    audit = Audit(user_id=user.id, url=str(body.url), result_json=result)
    db.add(audit)
    user.audit_count += 1
    db.commit()
    db.refresh(audit)
    return audit
