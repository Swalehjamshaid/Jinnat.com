import uvicorn
from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

# -------------------------
# ABSOLUTE IMPORTS
# -------------------------
from app.db import Base, engine, get_db
from app.models import User
from app.auth.router import router as auth_router
from app.api.router import router as api_router
from app.services.resend_admin import ensure_resend_ready
from app.audit.grader import compute_scores  # ✅ Fixed import

# -------------------------
# INIT APP
# -------------------------
app = FastAPI(title='FF Tech AI Website Audit SaaS')

# -------------------------
# Include Routers
# -------------------------
app.include_router(auth_router)
app.include_router(api_router)

# -------------------------
# Static & Templates
# -------------------------
app.mount('/static', StaticFiles(directory='app/static'), name='static')
templates = Jinja2Templates(directory='app/templates')

# -------------------------
# Startup Event
# -------------------------
@app.on_event('startup')
def on_startup():
    # Create tables
    Base.metadata.create_all(bind=engine)
    try:
        ensure_resend_ready()
    except Exception:
        # Ignore failures here to avoid blocking startup
        pass

# -------------------------
# Pages
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
    token: Optional[str] = request.cookies.get('session')
    user: Optional[User] = None

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
# FIX: Login Page Routes
# -------------------------
@app.get('/request-login', response_class=HTMLResponse)
async def show_login(request: Request):
    """Fixes the 404 error when users try to view the login page."""
    return templates.TemplateResponse(
        'index.html', 
        {"request": request}
    )

@app.post('/request-login')
async def handle_login(email: str = Form(...)):
    """Handles the magic link request from the form."""
    print(f"DEBUG: Login request for email: {email}")
    # Integration with your auth service would go here
    return JSONResponse({"message": "Magic link sent if email exists."})

# -------------------------
# API: Open Access Audit
# -------------------------
@app.post('/api/open-audit')
async def open_audit(request: Request):
    try:
        body = await request.json()
        url: Optional[str] = body.get('url')
        print(f"DEBUG: Starting audit for URL: {url}") # View this in Railway logs
        
        if not url:
            return JSONResponse({"detail": "URL is required"}, status_code=400)

        # -------------------------
        # Simulated audit data (replace with real crawler/fetch logic)
        # -------------------------
        onpage = {"missing_title_tags": 1, "missing_meta_descriptions": 2, "multiple_h1": 1}
        perf = {"lcp_ms": 2800, "fcp_ms": 1500, "mobile_score": 85, "desktop_score": 92}
        links = {"total_broken_links": 3}
        crawl_pages_count = 25

        # -------------------------
        # Compute scores using grader.py
        # -------------------------
        overall, grade, breakdown = compute_scores(onpage, perf, links, crawl_pages_count)

        # -------------------------
        # Extended world-class audit fields
        # -------------------------
        breakdown.update({
            "performance_mobile": perf.get('mobile_score', 0),
            "performance_desktop": perf.get('desktop_score', 0),
            "benchmark": 88,  # Industry benchmark
            "confidence": 95,  # Confidence %
            "competitor_score": 80,  # Simulated competitor score
        })

        # Final check: Ensure breakdown is not None so JS doesn't crash
        if breakdown is None:
            breakdown = {}

        print(f"DEBUG: Audit Success - Score: {overall}, Grade: {grade}")

        return JSONResponse({
            "overall_score": overall,
            "grade": grade,
            "breakdown": breakdown
        })

    except Exception as e:
        print(f"DEBUG ERROR: Audit failed with exception: {str(e)}")
        return JSONResponse({"detail": f"Audit failed: {str(e)}"}, status_code=500)

# -------------------------
# Local Run
# -------------------------
if __name__ == '__main__':
    # Using 8080 to match your current Railway container logs
    uvicorn.run(
        'app.main:app',
        host='0.0.0.0',
        port=8080,
        reload=True
    )
