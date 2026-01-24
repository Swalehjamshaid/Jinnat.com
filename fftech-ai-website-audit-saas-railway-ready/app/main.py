# app/main.py

import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.audit.grader import compute_scores # Ensure this import is correct

app = FastAPI(title='FF Tech AI Audit')

# Static and Template Setup
app.mount('/static', StaticFiles(directory='app/static'), name='static')
templates = Jinja2Templates(directory='app/templates')

# Route to serve the results page
@app.get('/audit-detail', response_class=HTMLResponse)
async def audit_detail(request: Request):
    return templates.TemplateResponse('audit_detail_open.html', {"request": request})

# Route to fix the 404 on login
@app.get('/request-login', response_class=HTMLResponse)
async def show_login(request: Request):
    return templates.TemplateResponse('index.html', {"request": request})

# THE CRITICAL API LINK
@app.post('/api/open-audit')
async def open_audit(request: Request):
    try:
        body = await request.json()
        url = body.get('url')
        
        if not url:
            return JSONResponse({"detail": "URL required"}, status_code=400)

        # Simulated Audit Data
        onpage = {"missing_title_tags": 1, "multiple_h1": 1}
        perf = {"lcp_ms": 2500}
        
        # Calculate scores
        overall, grade, breakdown = compute_scores(onpage, perf, {}, 25)

        # RESPONSE: This JSON structure MUST match your loadAudit() script
        return JSONResponse({
            "overall_score": overall,
            "grade": grade,
            "breakdown": breakdown
        })

    except Exception as e:
        print(f"Link Error: {e}")
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

if __name__ == '__main__':
    # Using 8080 to match Railway logs
    uvicorn.run('app.main:app', host='0.0.0.0', port=8080, reload=True)
