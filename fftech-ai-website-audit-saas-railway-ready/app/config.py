
from pydantic import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Core
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'change-me-in-env')
    BASE_URL: str = os.getenv('BASE_URL', 'http://127.0.0.1:8000')
    ENV: str = os.getenv('ENV', 'development')  # development|production

    # Database
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite:///./local.db')

    # Email (SMTP)
    SMTP_HOST: Optional[str] = os.getenv('SMTP_HOST')
    SMTP_PORT: Optional[int] = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER: Optional[str] = os.getenv('SMTP_USER')
    SMTP_PASS: Optional[str] = os.getenv('SMTP_PASS')
    SMTP_FROM: Optional[str] = os.getenv('SMTP_FROM')

    # Optional
    PSI_API_KEY: Optional[str] = os.getenv('PSI_API_KEY')

settings = Settings()

# Enforce DB URL on production
if settings.ENV.lower() == 'production' and not os.getenv('DATABASE_URL'):
    raise RuntimeError('DATABASE_URL is required in production (Railway provides this automatically when Postgres plugin is attached).')
