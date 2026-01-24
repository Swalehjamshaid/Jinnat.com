
# /app/app/main.py
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# If you split API routes, import them here
# from app.api.routes import router as api_router

app = FastAPI(title="FF Tech Audit")

# Static and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# If you use a separate router file, include it
# app.include_router(api_router)

# Optional: a simple healthcheck
@app.get("/healthz")
def healthz():
    return {"ok": True}
