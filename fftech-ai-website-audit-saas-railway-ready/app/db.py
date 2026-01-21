import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .settings import get_settings

settings = get_settings()

# 1. Clean the Database URL
# Railway provides postgres:// but SQLAlchemy 1.4+ requires postgresql://
db_url = settings.DATABASE_URL
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# 2. Configure Engine
# pool_pre_ping=True checks if the connection is alive before using it
# connect_args are only needed for local SQLite testing
engine = create_engine(
    db_url, 
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {}
)

# 3. Session and Base setup
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    Dependency to provide a database session to FastAPI routes.
    Ensures the connection is closed after every request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
