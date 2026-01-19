
# app/db.py
import os
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

Base = declarative_base()

def _add_ssl_and_timeouts(db_url: str) -> str:
    """
    Ensure sslmode=require and a short connect_timeout for managed Postgres (Railway).
    """
    if not db_url:
        raise ValueError("DATABASE_URL is missing. Set it in Railway → Variables.")

    parsed = urlparse(db_url)
    if parsed.scheme.startswith("postgres"):
        q = dict(parse_qsl(parsed.query))
        q.setdefault("sslmode", "require")       # Railway expects SSL
        q.setdefault("connect_timeout", "5")     # fail fast if unreachable
        new_query = urlencode(q)
        parsed = parsed._replace(query=new_query)
        return urlunparse(parsed)

    return db_url

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DATABASE_URL = _add_ssl_and_timeouts(DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,    # drop dead/stale connections automatically
    pool_recycle=1800,     # recycle every 30 mins
    pool_size=5,
    max_overflow=10,
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def try_connect_with_retries(retries: int = 5, delay_seconds: float = 2.0):
    """
    Call this in FastAPI startup to validate DB connectivity with brief retries.
    Avoids crashing on transient Railway cold starts.
    """
    import time
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError as e:
            last_error = e
            if attempt < retries:
                time.sleep(delay_seconds)
    raise last_error
