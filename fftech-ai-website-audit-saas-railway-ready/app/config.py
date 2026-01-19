import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    # These are read from environment variables in production
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite:///./local.db')
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'dev_secret_change_me')
    JWT_ALG: str = os.getenv('JWT_ALG', 'HS256')

settings = Settings()
