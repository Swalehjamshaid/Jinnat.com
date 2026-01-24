
# app/main.py
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router as api_router

app = FastAPI(title="FF Tech Audit")

# Static & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# API routes
app.include_router(api_router)

# Home
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
``
