import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "FF Tech AI Website Audit"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "generate-a-strong-secret-key-for-prod")
    JWT_ALG: str = "HS256"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    
    # SaaS Quotas
    FREE_AUDIT_LIMIT: int = 10
    
    # Email (For Passwordless Login)
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

settings = Settings()
