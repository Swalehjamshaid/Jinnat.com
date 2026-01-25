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

    # APIs
    GEMINI_API_KEY: str
    RESEND_API_KEY: str
    PSI_API_KEY: str | None = None

    # App
    PUBLIC_URL: str
    SECRET_KEY: str
    BRAND_NAME: str
    MAX_CRAWL_PAGES: int = 50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

def get_settings() -> Settings:
    return Settings()
