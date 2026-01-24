
# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from starlette.responses import HTMLResponse

# If you have API routes in app/api/routes.py, import them:
try:
    from app.api.routes import router as api_router  # optional
except Exception:
    api_router = None

app = FastAPI(title="FF Tech Audit")

# Static & templates (adjust paths if different)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Include API router if you have one
if api_router:
    app.include_router(api_router)
