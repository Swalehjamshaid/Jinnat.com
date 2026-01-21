from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import time

# Absolute imports for stability in Docker/Railway
from app.db import get_db
from app.models import User, Audit, Schedule
from app.schemas import AuditCreate, OpenAuditRequest, AuditOut
from app.audit.grader import run_audit  # FIXED: Changed from .runner to .grader
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
def open_audit(body: OpenAuditRequest, request: Request):
    from app.settings import get_settings
    settings = get_settings()
    ip = (request.client.host if request and request.client else 'anon')
    now = int(time.time())
    window = now // 3600
    key = f"{ip}:{window}"
    if not hasattr(open_audit, 'RATE_TRACK'):
        open_audit.RATE_TRACK = {}
    count = open_audit.RATE_TRACK.get(key, 0)
    if count >= settings.RATE_LIMIT_OPEN_PER_HOUR:
        raise HTTPException(429, 'Rate limit exceeded for open audits. Please try later or sign in.')
    open_audit.RATE_TRACK[key] = count + 1
    return run_audit(body.url)

@router.post('/audit', response_model=AuditOut)
def create_audit(body: AuditCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or not user.is_verified:
        raise HTTPException(401, 'Authentication required')
    from app.settings import get_settings
    settings = get_settings()
    if user.plan == 'free' and user.audit_count >= settings.FREE_AUDIT_LIMIT:
        raise HTTPException(403, f'Free plan limit reached ({settings.FREE_AUDIT_LIMIT} audits)')
    result = run_audit(body.url)
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

@router.post('/schedule')
def create_schedule(url: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(401, 'Authentication required')
    if user.plan == 'free':
        raise HTTPException(403, 'Subscription required to create schedules')
    sc = Schedule(user_id=user.id, url=url)
    db.add(sc)
    db.commit()
    return {"message": "Scheduled daily audit created", "id": sc.id}

@router.post('/competitor-audit')
def competitor_audit(body: AuditCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or not user.is_verified:
        raise HTTPException(401, 'Authentication required')
    base_url = str(body.url)
    competitors = [str(u) for u in (body.competitors or [])][:5]
    results = []
    base = run_audit(base_url)
    for cu in competitors:
        results.append({'url': cu, 'result': run_audit(cu)})
    comparison = {
        'overall':{
            'base': base.get('overall_score'),
            'competitors':[{'url': it['url'], 'score': it['result'].get('overall_score')} for it in results]
        },
        'performance':{
            'base': base.get('performance'),
            'competitors':[{'url': it['url'], 'performance': it['result'].get('performance')} for it in results]
        }
    }
    return {'base': {'url': base_url, 'result': base}, 'competitors': results, 'comparison': comparison}

@router.post('/competitor-report.pdf')
def competitor_report(body: AuditCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or not user.is_verified:
        raise HTTPException(401, 'Authentication required')
    base_url = str(body.url)
    competitors = [str(u) for u in (body.competitors or [])][:5]
    base = run_audit(base_url)
    results = []
    for cu in competitors:
        results.append({'url': cu, 'result': run_audit(cu)})
    comp_result = {'base': {'url': base_url, 'result': base}, 'competitors': results}
    from app.audit.competitor_report import build_competitor_pdf
    out_path = '/tmp/competitor_report.pdf'
    build_competitor_pdf(comp_result, out_path)
    return FileResponse(out_path, media_type='application/pdf', filename='competitor_report.pdf')

@router.get('/admin/resend-status')
def resend_status(request: Request):
    from app.settings import get_settings
    settings = get_settings()
    admins = [e.strip().lower() for e in (settings.ADMIN_EMAILS or '').split(',') if e.strip()]
    token = request.cookies.get('session')
    if not token:
        raise HTTPException(401, 'Authentication required')
    from app.auth.tokens import decode_token
    payload = decode_token(token)
    if not payload:
        raise HTTPException(401, 'Invalid token')
    email = (payload.get('sub') or '').lower()
    if admins and email not in admins:
        raise HTTPException(403, 'Admin only')
    from app.services.resend_admin import get_resend_domain_status
    return get_resend_domain_status()
