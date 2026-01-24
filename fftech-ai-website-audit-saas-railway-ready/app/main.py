import uvicorn
from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# ABSOLUTE IMPORTS
from app.db import Base, engine, get_db
from app.models import User
from app.auth.router import router as auth_router
from app.api.router import router as api_router
from app.services.resend_admin import ensure_resend_ready

# New: grader.py import
from app.grader import compute_scores

app = FastAPI(title='FF Tech AI Website Audit SaaS')

# -------------------------
# Include Routers (SAFE)
# -------------------------
app.include_router(auth_router)
app.include_router(api_router)

# -------------------------
# Static & Templates (SAFE)
# -------------------------
app.mount('/static', StaticFiles(directory='app/static'), name='static')
templates = Jinja2Templates(directory='app/templates')

# -------------------------
# Startup (SAFE)
# -------------------------
@app.on_event('startup')
def on_startup():
    Base.metadata.create_all(bind=engine)
    try:
        ensure_resend_ready()
    except Exception:
        pass

# -------------------------
# Pages (SAFE)
# -------------------------
@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        'index.html',
        {"request": request}
    )

@app.get('/dashboard', response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get('session')
    user = None

    if token:
        from app.auth.tokens import decode_token
        payload = decode_token(token)
        if payload:
            email = payload.get('sub')
            user = db.query(User).filter(User.email == email).first()

    return templates.TemplateResponse(
        'dashboard.html',
        {"request": request, "user": user}
    )

# -------------------------
# API: Open Access Audit
# -------------------------
@app.post('/api/open-audit')
async def open_audit(request: Request):
    try:
        body = await request.json()
        url = body.get('url')
        if not url:
            return JSONResponse({"detail": "URL is required"}, status_code=400)

        # -------------------------
        # Fetch audit data (simulate real audit)
        # -------------------------
        # Normally here you would call your crawler/analysis service.
        # For demonstration, we simulate dummy results:
        onpage = {"missing_title_tags": 1, "missing_meta_descriptions": 2, "multiple_h1": 1}
        perf = {"lcp_ms": 2800, "fcp_ms": 1500, "mobile_score": 85, "desktop_score": 92}
        links = {"total_broken_links": 3}
        crawl_pages_count = 25

        # -------------------------
        # Compute scores using grader.py
        # -------------------------
        overall, grade, breakdown = compute_scores(onpage, perf, links, crawl_pages_count)

        # Add extended fields for world-class audit
        breakdown['performance_mobile'] = perf.get('mobile_score', 0)
        breakdown['performance_desktop'] = perf.get('desktop_score', 0)
        breakdown['benchmark'] = 88  # Example: industry benchmark
        breakdown['confidence'] = 95  # Example: audit confidence %
        breakdown['competitor_score'] = 80  # Example: competitor simulation

        result = {
            "overall_score": overall,
            "grade": grade,
            "breakdown": breakdown
        }

        return JSONResponse(result)

    except Exception as e:
        return JSONResponse({"detail": f"Audit failed: {str(e)}"}, status_code=500)

# -------------------------
# Local run (SAFE)
# -------------------------
if __name__ == '__main__':
    uvicorn.run(
        'app.main:app',
        host='0.0.0.0',
        port=8000,
        reload=True
    )
