# app/audit/settings.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os

class Settings(BaseSettings):
    # --- Basic App Info ---
    APP_NAME: str = "FF Tech AI Website Audit SaaS"
    BRAND_NAME: str = "FF Tech"
    BRAND_LOGO_PATH: str = "app/static/img/fftech_logo.png"
    BASE_URL: str = "http://localhost:8000"
    
    # --- Database Configuration ---
    # Railway provides DATABASE_URL. We use it if present, otherwise fallback to local sqlite.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    
    # --- Security ---
    SECRET_KEY: str = "change-this-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 60 * 24

    # --- Email (SMTP & Resend) ---
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    MAIL_FROM: str = "reports@fftech.ai"

    RESEND_API_KEY: str = ""
    RESEND_FROM: str = ""
    EMAIL_PROVIDER: str = "auto"
    RESEND_DOMAIN: str = ""
    RESEND_ENFORCE_DKIM: bool = False
    RESEND_VERIFY_ON_STARTUP: bool = False

    ADMIN_EMAILS: str = ""

    # --- AI & External APIs ---
    # Integrated with your PSI logic and Gemini for future report generation
    GOOGLE_GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "models/gemini-2.0-flash" # Updated to current standard
    PSI_API_KEY: str = ""

    # --- Limits ---
    FREE_AUDIT_LIMIT: int = 10
    RATE_LIMIT_OPEN_PER_HOUR: int = 5

    # Pydantic v2 way to handle environment files
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache()
def get_settings() -> Settings:
    """Uses lru_cache to ensure we don't re-read the .env file on every call."""
    return Settings()
