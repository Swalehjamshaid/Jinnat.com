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
from app.settings import get_settings

router = APIRouter(prefix='/api', tags=['api'])

logger = logging.getLogger(__name__)

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
    Triggers the full 200-metric audit.
    No rate limit applied.
    """
    url_string = str(body.url)  # Ensure string type
    audit_result = run_audit(url_string)
    return audit_result


@router.get('/download-full-audit')
async def download_report(url: str = Query(...)):
    """
    Metric 10: Certified Export Readiness PDF.
    """
    url_string = str(url)
    report_data = run_audit(url_string)

    # Ensure reports directory exists
    os.makedirs('reports', exist_ok=True)
    file_path = f"reports/Audit_{int(time.time())}.pdf"

    # Generate PDF safely
    generate_full_audit_pdf(report_data, file_path)
    return FileResponse(path=file_path, filename="FFTech_Certified_Audit.pdf")


@router.post('/audit', response_model=AuditOut)
def create_audit(body: AuditCreate, request: Request, db: Session = Depends(get_db)):
    """
    Save audit results to database.
    """
    user = get_current_user(request, db)
    if not user: 
        raise HTTPException(401, 'Authentication required')
    
    url_string = str(body.url)
    result = run_audit(url_string)

    audit = Audit(user_id=user.id, url=url_string, result_json=result)
    db.add(audit)
    user.audit_count += 1
    db.commit()
    db.refresh(audit)
    return audit
