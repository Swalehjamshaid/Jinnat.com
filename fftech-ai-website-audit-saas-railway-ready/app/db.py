import os
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError
from .config import settings

Base = declarative_base()

def _add_ssl_and_timeouts(db_url: str) -> str:
    if not db_url:
        raise ValueError('DATABASE_URL is missing. Set it in Railway → Variables.')
    parsed = urlparse(db_url)
    if parsed.scheme.startswith('postgres'):
        q = dict(parse_qsl(parsed.query))
        q.setdefault('sslmode', 'require')
        q.setdefault('connect_timeout', '5')
        parsed = parsed._replace(query=urlencode(q))
        return urlunparse(parsed)
    return db_url

DATABASE_URL = _add_ssl_and_timeouts(settings.DATABASE_URL.strip()) if settings.DATABASE_URL else ''

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def try_connect_with_retries_and_create_tables(retries: int = 5, delay_seconds: float = 2.0):
    import time
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            print(f"[DB] Attempt {attempt}/{retries} connecting to database...")
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            print('[DB] Connection successful ✓')
            # Import models now to register with Base
            from . import models  # noqa: F401
            print('[DB] Creating tables (if not exist)...')
            Base.metadata.create_all(bind=engine)
            print('[DB] Tables created ✓')
            return
        except OperationalError as e:
            last_error = e
            if attempt < retries:
                print(f"[DB] Connection failed: {e}. Retrying in {delay_seconds}s...")
                time.sleep(delay_seconds)
    raise last_error
