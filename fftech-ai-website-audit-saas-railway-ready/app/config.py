import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    # --- APP IDENTITY ---
    BRAND_NAME: str = os.getenv("BRAND_NAME", "FF Tech")
    
    # --- DATABASE (The Missing Link) ---
    # This must match the name in your Railway Variables
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    
    # --- OTHER KEYS ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY")
    PUBLIC_URL: str = os.getenv("PUBLIC_URL", "http://localhost:8000")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "FF_TECH_SUPER_SECRET_TOKEN_2026")

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
