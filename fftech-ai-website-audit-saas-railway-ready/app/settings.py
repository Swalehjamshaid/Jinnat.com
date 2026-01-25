# app/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    PGHOST: str
    PGPASSWORD: str
    PGPORT: str = "5432"
    PGUSER: str
    POSTGRES_DB: str
    POSTGRES_PASSWORD: str
    POSTGRES_USER: str

    # API Keys
    AI_API_KEY: str
    GEMINI_API_KEY: str
    RESEND_API_KEY: str
    PSI_API_KEY: str

    # Public & secrets
    PUBLIC_URL: str
    SECRET_KEY: str
    BRAND_NAME: str

    # App config
    MAX_CRAWL_PAGES: int = 50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # ignore any unexpected env variables

# Singleton access
_settings_instance: Settings | None = None

def get_settings() -> Settings:
    global _settings_instance
    if not _settings_instance:
        _settings_instance = Settings()
    return _settings_instance
