# app/settings.py
from pydantic import BaseSettings
from typing import List

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./test.db"  # or your actual DB
    RATE_LIMIT_OPEN_PER_HOUR: int = 10
    FREE_AUDIT_LIMIT: int = 3

    # Fix for CORS
    ALLOWED_ORIGINS: List[str] = ["*"]  # You can restrict this to your frontend domains

    # Any other settings you need
    SECRET_KEY: str = "supersecretkey"

    class Config:
        env_file = ".env"  # optional, if you store settings in .env

def get_settings() -> Settings:
    return Settings()
