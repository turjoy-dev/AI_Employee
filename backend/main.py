"""Main application factory and entry point for AI Employee backend."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.api.router import api_router
from backend.api.routes import voice as voice_routes
from backend.core.config import get_settings
from backend.core.logging import get_logger, setup_logging
from backend.core.security import limiter
from backend.database.connection import check_db_connection, dispose_engine
from backend.database.init_db import init_db
from backend.schemas.health import RootResponse

settings = get_settings()
setup_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager handling startup and shutdown events."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version} [{settings.app_env}]...")
    
    # Initialize database tables and schema
    try:
        init_db()
        healthy, err = check_db_connection()
        if healthy:
            logger.info("Database connection established and verified.")
        else:
            logger.warning(f"Database connectivity warning at startup: {err}")
    except Exception as exc:
        logger.error(f"Fatal error during database startup initialization: {exc}", exc_info=True)
        raise

    yield

    # Clean shutdown tasks
    logger.info("Shutting down AI Employee application...")
    dispose_engine()
    logger.info("Application shutdown complete.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        description="AI Employee Backend Platform — Modular, Multi-Agent Business Automation",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure SlowAPI rate limiter and 429 exception handler
    limiter.reset()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Configure secure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Global Exception Handler for unhandled internal exceptions
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "detail": "An unexpected error occurred. Please contact system support.",
                "message": "An unexpected error occurred. Please contact system support.",
            },
        )

    # Mount API routers
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(
        voice_routes.router,
        prefix=f"{settings.api_v1_prefix}/voice",
    )

    # Root endpoint
    @app.get(
        "/",
        response_model=RootResponse,
        tags=["Root"],
        summary="Service metadata and navigation links",
    )
    def root() -> RootResponse:
        """Return core application metadata and documentation/health links."""
        return RootResponse(
            name=settings.app_name,
            version=settings.app_version,
            environment=settings.app_env,
            docs_url="/docs",
            health_check=f"{settings.api_v1_prefix}/health",
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.app_debug,
    )
