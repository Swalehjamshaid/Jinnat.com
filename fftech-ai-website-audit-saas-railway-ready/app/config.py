# app/config.py
import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    BRAND_NAME: str = "FF Tech"
    # ... other settings ...
    
    # ADD THIS LINE:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY") 

    class Config:
        env_file = ".env"

settings = Settings()
