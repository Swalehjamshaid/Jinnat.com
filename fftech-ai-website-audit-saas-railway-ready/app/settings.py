# app/settings.py
import os
import json
from functools import lru_cache
from pydantic_settings import BaseSettings
from google.oauth2 import service_account

class Settings(BaseSettings):
    APP_NAME: str = "FF Tech AI Website Audit"
    
    # DATABASE_URL handling for Railway
    _db_url: str = os.environ.get("DATABASE_URL", "sqlite:///./test.db")
    @property
    def DATABASE_URL(self) -> str:
        if self._db_url.startswith("postgres://"):
            return self._db_url.replace("postgres://", "postgresql://", 1)
        return self._db_url

    # API Keys from Railway Variables
    PSI_API_KEY: str = os.environ.get("PSI_API_KEY", "")
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")

    @property
    def gcp_credentials(self):
        """Fixes the double-backslash issue in the Railway Private Key."""
        creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if not creds_json:
            return None
        try:
            creds_dict = json.loads(creds_json)
            if "private_key" in creds_dict:
                # Cleans the key format for Google
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\\\n", "\n").replace("\\n", "\n")
            return service_account.Credentials.from_service_account_info(creds_dict)
        except Exception as e:
            return None

@lru_cache()
def get_settings():
    return Settings()
