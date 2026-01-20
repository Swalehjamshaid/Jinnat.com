from fastapi import FastAPI, Depends, Request, HTTPException, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from .db import get_db, try_connect_with_retries_and_create_tables
from .models import User, Audit
from .config import settings
from .audit.compute import audit_site_sync
from .report.report import build_pdf
import jwt

app = FastAPI(title="FF Tech AI Website Audit")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
def startup(): try_connect_with_retries_and_create_tables()

def get_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session")
    if not token: return None
    try:
        data = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALG])
        return db.get(User, int(data["sub"]))
    except: return None

@app.post("/api/audit")
async def run_audit(url: str, db: Session = Depends(get_db), user: User = Depends(get_user)):
    if user and not user.is_paid:
        if db.query(Audit).filter(Audit.user_id == user.id).count() >= settings.FREE_AUDIT_LIMIT:
            raise HTTPException(402, "Limit reached. Upgrade to Premium.")
    
    result = audit_site_sync(url)
    if user:
        audit = Audit(user_id=user.id, url=url, score=result['overall']['score'], grade=result['overall']['grade'], metrics=result['metrics'], summary=result['summary'])
        db.add(audit); db.commit(); db.refresh(audit)
        result["id"] = audit.id
    else: result["id"] = 0
    return result

@app.get("/api/report/pdf/{audit_id}")
async def get_pdf(audit_id: int, db: Session = Depends(get_db), user: User = Depends(get_user)):
    if audit_id == 0: raise HTTPException(403, "Register to download")
    audit = db.get(Audit, audit_id)
    content = build_pdf({"overall": {"score": audit.score, "grade": audit.grade}, "metrics": audit.metrics, "summary": audit.summary})
    return Response(content, media_type="application/pdf")
