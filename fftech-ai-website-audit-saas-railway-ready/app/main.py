# app/main.py
from __future__ import annotations

import os
import time
import logging
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware


# -----------------------------------------------------------------------------
# Logging (simple, container-friendly)
# -----------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("app")


# -----------------------------------------------------------------------------
# Lightweight config (no extra dependency required)
# -----------------------------------------------------------------------------
class Settings:
    """
    Flexible settings using env vars.
    You can later replace this with pydantic-settings if you want.
    """
    APP_NAME: str = os.getenv("APP_NAME", "FFTech Audit API")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    ENV: str = os.getenv("ENV", "production")  # dev/staging/production
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes", "on")

    # CORS
    CORS_ALLOW_ORIGINS: str = os.getenv("CORS_ALLOW_ORIGINS", "*")  # comma-separated

    # OpenAPI docs toggles (recommended to disable in production if needed)
    ENABLE_DOCS: bool = os.getenv("ENABLE_DOCS", "true").lower() in ("1", "true", "yes", "on")

    # API base path (helps when running behind reverse proxy)
    ROOT_PATH: str = os.getenv("ROOT_PATH", "")

    # Feature flags
    ENABLE_AUDIT_ROUTES: bool = os.getenv("ENABLE_AUDIT_ROUTES", "true").lower() in ("1", "true", "yes", "on")


settings = Settings()


# -----------------------------------------------------------------------------
# Application factory (very flexible, testable, avoids circular imports)
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
    # Middleware: CORS
    # --------------------------
    origins = [o.strip() for o in settings.CORS_ALLOW_ORIGINS.split(",") if o.strip()]
    if origins == ["*"]:
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
        duration_ms = int((time.time() - start) * 1000)
        response.headers["X-Process-Time-ms"] = str(duration_ms)
        return response

    # --------------------------
    # Lifecycle events (startup/shutdown)
    # --------------------------
    @app.on_event("startup")
    async def on_startup():
        logger.info("Starting %s v%s (ENV=%s)", settings.APP_NAME, settings.APP_VERSION, settings.ENV)
        # Example: init DB connections, load models, warm caches, etc.
        # Keep it light; avoid importing heavy modules at file import-time.

    @app.on_event("shutdown")
    async def on_shutdown():
        logger.info("Shutting down %s", settings.APP_NAME)
        # Example: close DB connections, cleanup resources

    # --------------------------
    # Global exception handlers
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
    # Health endpoints (great for Docker/K8s)
    # --------------------------
    @app.get("/health", tags=["system"])
    async def health():
        return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}

    @app.get("/ready", tags=["system"])
    async def ready():
        # Add checks here (db reachable, external deps, etc.)
        return {"status": "ready"}

    # --------------------------
    # Routes / Routers (lazy import to prevent circular imports)
    # --------------------------
    if settings.ENABLE_AUDIT_ROUTES:
        try:
            # Import routers only after app creation to avoid circular import issues.
            # Example: from app.routes.audit import router as audit_router
            # app.include_router(audit_router, prefix="/api/v1", tags=["audit"])

            # If you don't have routers yet, keep this placeholder.
            logger.info("Audit routes enabled (ENABLE_AUDIT_ROUTES=true)")

        except Exception as e:
            logger.exception("Failed to load routes: %s", e)
            # Don't crash the whole app if routes fail in production
            # but you may choose to raise e in strict environments.

    # --------------------------
    # Simple root route
    # --------------------------
    @app.get("/", tags=["system"])
    async def root():
        return {
            "message": f"Welcome to {settings.APP_NAME}",
            "docs": "/docs" if settings.ENABLE_DOCS else None,
            "health": "/health",
        }

    return app


# -----------------------------------------------------------------------------
# ASGI entrypoint: Uvicorn expects `app` here
# -----------------------------------------------------------------------------
app = create_app()
