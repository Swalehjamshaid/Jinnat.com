# app/db.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .settings import get_settings

settings = get_settings()

# Determine if we are using SQLite (local) or PostgreSQL (Railway)
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# Create the engine with appropriate arguments for the database type
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if is_sqlite else {}
)

# SessionLocal is the factory that creates new database sessions for each request
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our database models (User, Audit, etc.)
Base = declarative_base()

def get_db():
    """
    Dependency to provide a database session to FastAPI routes.
    Ensures the connection is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
