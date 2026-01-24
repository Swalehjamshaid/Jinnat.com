# app/settings.py
import os
import json
import logging
from functools import lru_cache
from typing import Optional

from pydantic import BaseSettings, Field, validator
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """
    Application settings for FF Tech AI Website Audit SaaS.
    Automatically loaded from environment variables.
    """

    APP_NAME: str = "FF Tech AI Website Audit"

    # Database URL: Railway or local fallback
    DATABASE_URL: str = Field(default="sqlite:///./test.db", env="DATABASE_URL")

    # API Keys
    PSI_API_KEY: str = Field(default="", env="PSI_API_KEY")
    GEMINI_API_KEY: str = Field(default="", env="GEMINI_API_KEY")

    # Google Cloud Credentials JSON
    GOOGLE_APPLICATION_CREDENTIALS_JSON: Optional[str] = Field(default=None, env="GOOGLE_APPLICATION_CREDENTIALS_JSON")

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
    def gcp_credentials(self) -> Optional[service_account.Credentials]:
        """
        Returns Google Cloud credentials object from JSON environment variable.
        Handles double-backslash issues in private_key.
        """
        creds_json = self.GOOGLE_APPLICATION_CREDENTIALS_JSON
        if not creds_json:
            logger.warning("Google Application Credentials JSON not provided.")
            return None

        try:
            creds_dict = json.loads(creds_json)
            if "private_key" in creds_dict:
                # Fix formatting issues with the private key
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\\\n", "\n").replace("\\n", "\n")
            return service_account.Credentials.from_service_account_info(creds_dict)
        except json.JSONDecodeError:
            logger.error("Failed to decode GOOGLE_APPLICATION_CREDENTIALS_JSON")
        except Exception as e:
            logger.error(f"Error initializing GCP credentials: {e}")
        return None


# Cached singleton to avoid repeated instantiation
@lru_cache()
def get_settings() -> Settings:
    return Settings()
