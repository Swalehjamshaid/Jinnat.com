import os
import time
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

Base = declarative_base()

def _prepare_url(db_url: str) -> str:
    if not db_url:
        raise ValueError("DATABASE_URL is missing in environment variables.")
    # FIX: SQLAlchemy 2.0 requires 'postgresql://' dialect
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    parsed = urlparse(db_url)
    if "postgresql" in parsed.scheme:
        q = dict(parse_qsl(parsed.query))
        q.setdefault("sslmode", "require")
        q.setdefault("connect_timeout", "5")
        parsed = parsed._replace(query=urlencode(q))
        return urlunparse(parsed)
    return db_url

DATABASE_URL = _prepare_url(os.getenv("DATABASE_URL", "").strip())

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def try_connect_with_retries_and_create_tables(retries: int = 5, delay: float = 2.0):
    # IMPORTANT: Import models here so Base knows they exist
    from . import models 
    for attempt in range(1, retries + 1):
        try:
            print(f"[DB] Attempt {attempt} connecting...")
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()
            Base.metadata.create_all(bind=engine)
            print("[DB] Tables synced successfully ✓")
            return
        except Exception as e:
            if attempt == retries: raise e
            time.sleep(delay)
