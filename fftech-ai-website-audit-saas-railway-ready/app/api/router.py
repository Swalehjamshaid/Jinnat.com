from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import time
import os

from app.db import get_db
from app.models import User, Audit
from app.schemas import AuditCreate, OpenAuditRequest, AuditOut
from app.audit.grader import run_audit
from app.services.pdf_generator import generate_full_audit_pdf
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


def safe_run_audit(url: str) -> dict:
    """
    Safely run the audit and ensure a dictionary is always returned.
    Prevents 'str' object has no attribute 'get' errors.
    """
    try:
        result = run_audit(url)
        if not isinstance(result, dict):
            # fallback: always return a proper dictionary
            result = {
                "url": url,
                "overall_score": 0,
                "grade": "N/A",
                "categories": {}
            }
        else:
            # Ensure all required keys exist
            result.setdefault("url", url)
            result.setdefault("overall_score", 0)
            result.setdefault("grade", "N/A")
            result.setdefault("categories", {})
    except Exception as e:
        print(f"Audit failed for URL {url}: {e}")
        result = {
            "url": url,
            "overall_score": 0,
            "grade": "N/A",
            "categories": {}
        }
    return result


@router.post('/open-audit')
async def open_audit(body: OpenAuditRequest, request: Request):
    """Triggers the 200-metric audit suite."""
    from app.settings import get_settings
    settings = get_settings()

    ip = request.client.host if request and request.client else 'anon'
    key = f"{ip}:{int(time.time()) // 3600}"

    if not hasattr(open_audit, 'RATE_TRACK'):
        open_audit.RATE_TRACK = {}
    count = open_audit.RATE_TRACK.get(key, 0)

    if count >= settings.RATE_LIMIT_OPEN_PER_HOUR:
        raise HTTPException(429, 'Rate limit exceeded.')

    open_audit.RATE_TRACK[key] = count + 1

    # Ensure URL is string
    url_string = str(body.url)
    return safe_run_audit(url_string)


@router.get('/download-full-audit')
async def download_report(url: str = Query(...)):
    """Metric 10: Certified Export Readiness."""
    url_string = str(url)
    report_data = safe_run_audit(url_string)

    if not os.path.exists('reports'):
        os.makedirs('reports')
    file_path = f"reports/Audit_{int(time.time())}.pdf"
    generate_full_audit_pdf(report_data, file_path)
    return FileResponse(path=file_path, filename="FFTech_Certified_Audit.pdf")


@router.post('/audit', response_model=AuditOut)
def create_audit(body: AuditCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(401, 'Authentication required')

    url_string = str(body.url)
    result = safe_run_audit(url_string)

    audit = Audit(user_id=user.id, url=url_string, result_json=result)
    db.add(audit)
    user.audit_count += 1
    db.commit()
    db.refresh(audit)
    return audit
