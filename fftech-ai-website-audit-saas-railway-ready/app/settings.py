# app/settings.py
import os
import json
import logging
from functools import lru_cache
from typing import Optional

from pydantic import BaseSettings, Field, validator

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application settings for FF Tech AI Website Audit SaaS.
    Fully Python-based, no Google dependencies.
    """

    APP_NAME: str = "FF Tech AI Website Audit"

    # Database URL: Railway or local fallback
    DATABASE_URL: str = Field(default="sqlite:///./test.db", env="DATABASE_URL")

    # API Keys (optional, fully Python)
    PSI_API_KEY: str = Field(default="", env="PSI_API_KEY")
    GEMINI_API_KEY: str = Field(default="", env="GEMINI_API_KEY")

    # Optional JSON credentials (now just stored as dict for Python use)
    CREDENTIALS_JSON: Optional[str] = Field(default=None, env="CREDENTIALS_JSON")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("DATABASE_URL", pre=True)
    def normalize_postgres_url(cls, v: str) -> str:
        """
        Converts old-style postgres URLs from 'postgres://' to 'postgresql://'.
        """
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    @property
    def credentials(self) -> Optional[dict]:
        """
        Returns credentials JSON as a Python dictionary (if provided).
        """
        creds_json = self.CREDENTIALS_JSON
        if not creds_json:
            logger.info("No credentials JSON provided.")
            return None

        try:
            creds_dict = json.loads(creds_json)
            # Fix common escaped newlines in keys
            for key in ["private_key", "client_email"]:
                if key in creds_dict and isinstance(creds_dict[key], str):
                    creds_dict[key] = creds_dict[key].replace("\\\\n", "\n").replace("\\n", "\n")
            return creds_dict
        except json.JSONDecodeError:
            logger.error("Failed to decode CREDENTIALS_JSON")
        except Exception as e:
            logger.error(f"Error parsing credentials JSON: {e}")
        return None


# Cached singleton to avoid repeated instantiation
@lru_cache()
def get_settings() -> Settings:
    return Settings()
