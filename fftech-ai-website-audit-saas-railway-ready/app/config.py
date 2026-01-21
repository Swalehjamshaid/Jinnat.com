import os
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    # Fixes the 'at least 32 characters' error
    SECRET_KEY: str = Field(
        "7e7c9f6d8a4b2c1e5f9a0d3b2c1e5f9a8d7c6b5a4f3e2d1c", 
        env="SECRET_KEY",
        min_length=32
    )
    
    # Database URL from Railway
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    
    # App Settings
    FREE_AUDIT_LIMIT: int = 3
    RATE_LIMIT_OPEN_PER_HOUR: int = 5
    BRAND_LOGO_PATH: str = "static/img/fftech_logo.png"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

def get_settings():
    return settings
