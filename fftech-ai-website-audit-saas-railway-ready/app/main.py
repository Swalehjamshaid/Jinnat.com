import os
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from .config import settings
from .database import init_db, SessionLocal
from .models import User, Audit
from .routers import auth as auth_router
from .audit.analyzer import analyze
from .audit.grader import overall_score, to_grade
from .audit.report import build_pdf

app = FastAPI(title=f"{settings.BRAND_NAME} AI Website Audit")

# CORS and Static Files setup
app.add_middleware(
    CORSMiddleware, 
    allow_origins=['*'], 
    allow_credentials=True, 
    allow_methods=['*'], 
    allow_headers=['*']
)

# Setup directories
static_dir = os.path.join(os.path.dirname(__file__), 'static')
app.mount('/static', StaticFiles(directory=static_dir), name='static')
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), 'templates'))

app.include_router(auth_router.router)

@app.on_event('startup')
def on_startup():
    init_db()
    # Required for Railway to store PDFs
    os.makedirs('storage/reports', exist_ok=True)
    os.makedirs('storage/exports', exist_ok=True)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- GOOGLE VERIFICATION ROUTE ---
# This serves your specific verification code directly to Google
@app.get('/googlee889836d4b830bda.html', response_class=PlainTextResponse)
async def google_verify():
    return "google-site-verification: googlee889836d4b830bda.html"

# --- UI PAGES ---
@app.get('/')
async def index(request: Request):
    return templates.TemplateResponse('index.html', {"request": request})

@app.get('/open-audit')
async def open_audit_page(request: Request):
    return templates.TemplateResponse('open_audit.html', {"request": request})

@app.get('/login')
async def login_page(request: Request):
    return templates.TemplateResponse('login.html', {"request": request})

@app.get('/register')
async def register_page(request: Request):
    return templates.TemplateResponse('register.html', {"request": request})

@app.get('/dashboard')
async def dashboard_page(request: Request):
    return templates.TemplateResponse('dashboard.html', {"request": request})

@app.get('/audit_detail')
async def audit_detail_page(request: Request, id: int | None = None):
    return templates.TemplateResponse('audit_detail.html', {"request": request, "id": id})

# --- API ENDPOINTS ---
from .schemas import AuditRequest, AuditResponse

@app.post('/api/audit', response_model=AuditResponse)
async def run_audit(payload: AuditRequest, db: Session = Depends(get_db), email: str | None = None):
    url = payload.url.strip()
    if not (url.startswith('http://') or url.startswith('https://')):
        raise HTTPException(status_code=400, detail='URL must start with http:// or https://')
    
    result = await analyze(url, payload.competitors)
    ovr = overall_score(result['category_scores'])
    grade = to_grade(ovr)
    
    summary = {'executive_summary': f'Comprehensive AI audit for {url}.', 'strengths': ['Verified'], 'weaknesses': ['Optimization needed'], 'priority_fixes': ['Fix links']}
    
    audit_id = None
    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            audit = Audit(user_id=user.id, url=url, overall_score=ovr, grade=grade, summary=summary, category_scores=result['category_scores'], metrics=result['metrics'])
            db.add(audit); db.commit(); db.refresh(audit)
            audit_id = audit.id
            
            # Generate and Save PDF Path
            pdf_path = build_pdf(audit.id, url, ovr, grade, result['category_scores'], result['metrics'], out_dir='storage/reports')
            audit.report_pdf_path = pdf_path
            db.commit()
            
    return AuditResponse(audit_id=audit_id, url=url, overall_score=ovr, grade=grade, summary=summary, category_scores=result['category_scores'], metrics=result['metrics'])

@app.get('/api/reports/pdf/{audit_id}')
async def get_pdf(audit_id: int, db: Session = Depends(get_db)):
    a = db.query(Audit).filter(Audit.id == audit_id).first()
    if not a or not a.report_pdf_path:
        raise HTTPException(status_code=404, detail='PDF Report not found')
    return FileResponse(a.report_pdf_path, media_type='application/pdf', filename=f'FF_Tech_Report_{audit_id}.pdf')
