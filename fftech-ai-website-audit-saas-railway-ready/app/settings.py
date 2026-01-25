# app/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # -----------------------------
    # PostgreSQL / Database Settings
    # -----------------------------
    pguser: str = "postgres"
    pgpassword: str = "OyukiGQaJmjLuEiXSOizcUEMleaTLBjtj"
    pghost: str = "postgres.railway.internal"
    pgport: int = 5432
    postgres_db: str = "railway"

    # -----------------------------
    # General App Settings
    # -----------------------------
    max_crawl_pages: int = 50
    brand_name: str = "FF Tech"
    public_url: str = "https://example.com"
    secret_key: str = "FF_TECH_SUPER_SECRET_TOKEN_2026"
    ai_api_key: str = "AIzaSyDOLkFHWKT8cnva1SizcHgdAGmhUaf3KJ4"

    # -----------------------------
    # Optional: allow extra keys without crashing
    # -----------------------------
    model_config = {
        "extra": "allow"
    }


def get_settings() -> Settings:
    """
    Returns a Settings instance.
    Any extra environment variables are allowed but ignored.
    """
    return Settings()
