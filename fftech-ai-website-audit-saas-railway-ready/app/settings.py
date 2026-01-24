import os
import json
from functools import lru_cache
from pydantic_settings import BaseSettings
from google.oauth2 import service_account

class Settings(BaseSettings):
    APP_NAME: str = "FF Tech AI Audit"
    # Railway Postgres URL fix
    _db_url: str = os.environ.get("DATABASE_URL", "sqlite:///./test.db")
    @property
    def DATABASE_URL(self) -> str:
        if self._db_url.startswith("postgres://"):
            return self._db_url.replace("postgres://", "postgresql://", 1)
        return self._db_url

    PSI_API_KEY: str = os.environ.get("PSI_API_KEY", "")

    @property
    def gcp_credentials(self):
        creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if not creds_json: return None
        try:
            creds_dict = json.loads(creds_json)
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\\\n", "\n").replace("\\n", "\n")
            return service_account.Credentials.from_service_account_info(creds_dict)
        except Exception as e:
            return None

@lru_cache()
def get_settings():
    return Settings()
