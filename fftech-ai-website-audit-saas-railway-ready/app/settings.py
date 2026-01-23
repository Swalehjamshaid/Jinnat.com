
from pydantic import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "FF Tech AI Website Audit SaaS"
    BASE_URL: str = "http://localhost:8000"
    DATABASE_URL: str = "sqlite:///./app.db"
    SECRET_KEY: str = "change-this-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

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

    GOOGLE_GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "models/gemini-2.5-flash"

    PSI_API_KEY: str = ""

    FREE_AUDIT_LIMIT: int = 10
    RATE_LIMIT_OPEN_PER_HOUR: int = 5

    BRAND_NAME: str = "FF Tech"
    BRAND_LOGO_PATH: str = "app/static/img/fftech_logo.png"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> 'Settings':
    return Settings()
