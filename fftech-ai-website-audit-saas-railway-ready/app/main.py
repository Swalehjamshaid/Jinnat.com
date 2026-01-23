from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import router as api_router
from app.settings import get_settings

settings = get_settings()
app = FastAPI(
    title="FFTech AI Website Audit SaaS",
    version="1.0.0",
    description="Website auditing SaaS API ready for Railway deployment"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "FFTech AI Website Audit SaaS is running 🚀"}
