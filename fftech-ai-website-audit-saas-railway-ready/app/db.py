
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Debug: show DB (sanitized)
try:
    safe = settings.DATABASE_URL.split('@')[-1]
    print(f"[DB] Using database: postgresql://***@{safe}" if 'postgresql' in settings.DATABASE_URL else f"[DB] Using database: {settings.DATABASE_URL}")
except Exception:
    pass
