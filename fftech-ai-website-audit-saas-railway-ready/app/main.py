# app/main.py

import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
# Make sure your folder is named 'app' and has an 'audit' folder with 'grader.py' inside
from app.audit.grader import compute_scores 

app = FastAPI(title='FF Tech AI Audit')

# ---------------------------------------------------------
# Static and Template Setup
# ---------------------------------------------------------
app.mount('/static', StaticFiles(directory='app/static'), name='static')
templates = Jinja2Templates(directory='app/templates')

# ---------------------------------------------------------
# Page Routes (GET)
# ---------------------------------------------------------

# FIX: Added the root route to stop the 404 error in your logs
@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    """Serve the landing page/main audit input page."""
    return templates.TemplateResponse('index.html', {"request": request})

@app.get('/audit-detail', response_class=HTMLResponse)
async def audit_detail(request: Request):
    """Serve the detailed results page."""
    return templates.TemplateResponse('audit_detail_open.html', {"request": request})

@app.get('/request-login', response_class=HTMLResponse)
async def show_login(request: Request):
    """Serve the login/index page for magic link requests."""
    return templates.TemplateResponse('index.html', {"request": request})

# ---------------------------------------------------------
# API Routes (POST)
# ---------------------------------------------------------

@app.post('/api/open-audit')
async def open_audit(request: Request):
    """The critical API bridge that processes the audit."""
    try:
        body = await request.json()
        url = body.get('url')
        
        if not url:
            return JSONResponse({"detail": "URL required"}, status_code=400)

        # Simulated Audit Data (This flows into grader.py)
        onpage = {"missing_title_tags": 1, "multiple_h1": 1}
        perf = {"lcp_ms": 2500}
        
        # Calculate scores using the imported grader logic
        overall, grade, breakdown = compute_scores(onpage, perf, {}, 25)

        # RESPONSE: Structure must match the 'loadAudit' JS function keys
        return JSONResponse({
            "overall_score": overall,
            "grade": grade,
            "breakdown": breakdown
        })

    except Exception as e:
        # Logs the error to your Railway terminal for debugging
        print(f"Audit Link Error: {e}")
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

@app.post('/request-login')
async def handle_login(email: str = Form(...)):
    """Handles the magic link form submission."""
    return JSONResponse({"message": f"Magic link sent to {email} if registered."})

# ---------------------------------------------------------
# Server Execution
# ---------------------------------------------------------
if __name__ == '__main__':
    # Port 8080 is standard for Railway deployments
    uvicorn.run('app.main:app', host='0.0.0.0', port=8080, reload=True)
