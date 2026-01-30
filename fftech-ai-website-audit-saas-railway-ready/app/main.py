# app/main.py
from __future__ import annotations

import os
import time
import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware

try:
    # Optional dependency (FastAPI usually has it)
    from fastapi.staticfiles import StaticFiles
except Exception:  # pragma: no cover
    StaticFiles = None  # type: ignore


# -----------------------------------------------------------------------------
# Logging (container-friendly)
# -----------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("app")


# -----------------------------------------------------------------------------
# Simple settings (env-based; replace with pydantic-settings later if desired)
# -----------------------------------------------------------------------------
class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "FFTech Audit API")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    ENV: str = os.getenv("ENV", "production")  # dev/staging/production
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes", "on")

    # Docs exposure
    ENABLE_DOCS: bool = os.getenv("ENABLE_DOCS", "true").lower() in ("1", "true", "yes", "on")

    # When behind reverse proxy subpath
    ROOT_PATH: str = os.getenv("ROOT_PATH", "")

    # CORS
    CORS_ALLOW_ORIGINS: str = os.getenv("CORS_ALLOW_ORIGINS", "*")  # comma-separated

    # API prefix
    API_PREFIX: str = os.getenv("API_PREFIX", "/api")
    API_VERSION_PREFIX: str = os.getenv("API_VERSION_PREFIX", "/v1")

    # Feature flags
    ENABLE_AUDIT_ROUTES: bool = os.getenv("ENABLE_AUDIT_ROUTES", "true").lower() in ("1", "true", "yes", "on")

    # Static directory
    STATIC_DIR: str = os.getenv("STATIC_DIR", "app/static")


settings = Settings()


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _truthy(value: Any) -> bool:
    return str(value).lower() in ("1", "true", "yes", "on")


def _split_csv(value: str) -> list[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


# -----------------------------------------------------------------------------
# App factory (flexible + avoids circular import issues)
# -----------------------------------------------------------------------------
def create_app() -> FastAPI:
    docs_url = "/docs" if settings.ENABLE_DOCS else None
    redoc_url = "/redoc" if settings.ENABLE_DOCS else None
    openapi_url = "/openapi.json" if settings.ENABLE_DOCS else None

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        root_path=settings.ROOT_PATH,
    )

    # --------------------------
    # CORS
    # --------------------------
    origins = _split_csv(settings.CORS_ALLOW_ORIGINS)
    if not origins or origins == ["*"]:
        allow_origins = ["*"]
    else:
        allow_origins = origins

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --------------------------
    # Request timing middleware
    # --------------------------
    @app.middleware("http")
    async def add_timing_header(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        response.headers["X-Process-Time-ms"] = str(int((time.time() - start) * 1000))
        return response

    # --------------------------
    # Global exception handler
    # --------------------------
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error: %s %s", request.method, request.url)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "detail": str(exc) if settings.DEBUG else "An unexpected error occurred.",
            },
        )

    # --------------------------
    # Lifecycle events
    # --------------------------
    @app.on_event("startup")
    async def on_startup():
        logger.info("Starting %s v%s (ENV=%s)", settings.APP_NAME, settings.APP_VERSION, settings.ENV)

        # Mount static files if directory exists and StaticFiles is available
        static_dir = Path(settings.STATIC_DIR)
        if StaticFiles is not None and static_dir.exists() and static_dir.is_dir():
            app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
            logger.info("Static mounted: /static -> %s", static_dir)

        # Lazy-load routers safely (prevents circular import & startup crashes)
        _include_routers(app)

    @app.on_event("shutdown")
    async def on_shutdown():
        logger.info("Shutting down %s", settings.APP_NAME)

    # --------------------------
    # System endpoints
    # --------------------------
    @app.get("/", tags=["system"])
    async def root():
        return {
            "message": f"Welcome to {settings.APP_NAME}",
            "version": settings.APP_VERSION,
            "docs": "/docs" if settings.ENABLE_DOCS else None,
            "health": "/health",
            "ready": "/ready",
        }

    @app.get("/health", tags=["system"])
    async def health():
        return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}

    @app.get("/ready", tags=["system"])
    async def ready():
        # Add real checks here later (db ping, redis, etc.)
        return {"status": "ready"}

    # --------------------------
    # Favicon handler (prevents browser 404 noise)
    # --------------------------
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        """
        If app/static/favicon.ico exists -> serve it.
        Otherwise return 204 (No Content) to avoid 404 log noise.
        """
        ico = Path(settings.STATIC_DIR) / "favicon.ico"
        if ico.exists():
            return FileResponse(str(ico))
        return Response(status_code=204)

    return app


def _include_routers(app: FastAPI) -> None:
    """
    Router loader. Keeps main.py stable even if modules aren't present yet.
    Add your routers here as your project grows.

    IMPORTANT: We import inside the function to avoid circular imports.
    """
    api_prefix = settings.API_PREFIX + settings.API_VERSION_PREFIX

    if settings.ENABLE_AUDIT_ROUTES:
        try:
            # Example structure (recommended):
            # app/routes/audit.py -> router = APIRouter()
            # from app.routes.audit import router as audit_router

            from app.routes.audit import router as audit_router  # type: ignore

            app.include_router(audit_router, prefix=api_prefix, tags=["audit"])
            logger.info("Audit routes loaded at %s", api_prefix)
        except ModuleNotFoundError:
            # Routes module not created yet — not an error.
            logger.info("Audit routes enabled (ENABLE_AUDIT_ROUTES=true) but app.routes.audit not found (skipping).")
        except Exception as e:
            # You can raise here if you want strict behavior
            logger.exception("Failed to load audit routes: %s", e)


# -----------------------------------------------------------------------------
# ASGI entrypoint (Uvicorn expects `app`)
# -----------------------------------------------------------------------------
app = create_app()
