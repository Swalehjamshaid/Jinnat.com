import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Identity
    APP_NAME: str = "FF Tech AI Website Audit"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key-123")
    JWT_ALG: str = "HS256"
    
    # Database (Your db.py will handle the URL normalization)
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    
    # SaaS Limits
    FREE_AUDIT_LIMIT: int = 10

settings = Settings()
