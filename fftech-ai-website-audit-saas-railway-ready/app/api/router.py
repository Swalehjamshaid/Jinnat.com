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

@router.post('/open-audit')
async def open_audit(body: OpenAuditRequest, request: Request):
    settings = get_settings()
    ip = (request.client.host if request and request.client else 'anon')
    
    import time
    now = int(time.time())
    window = now // 3600
    key = f"{ip}:{window}"
    
    if not hasattr(open_audit, 'RATE_TRACK'):
        open_audit.RATE_TRACK = {}
    
    count = open_audit.RATE_TRACK.get(key, 0)
    if count >= settings.RATE_LIMIT_OPEN_PER_HOUR:
        raise HTTPException(429, 'Rate limit exceeded')
    
    open_audit.RATE_TRACK[key] = count + 1
    return await run_audit(body.url)

@router.post('/audit', response_model=AuditOut)
async def create_audit(body: AuditCreate, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).first() # Simplified for example
    result = await run_audit(body.url)
    audit = Audit(user_id=user.id, url=str(body.url), result_json=result)
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit
