"""Health check route verifying application state and database connectivity."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.core.config import Settings, get_settings
from backend.core.logging import get_logger
from backend.database.connection import get_db
from backend.schemas.health import DatabaseHealthInfo, HealthResponse

router = APIRouter(tags=["Health"])
logger = get_logger(__name__)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health and database connectivity check",
    responses={
        status.HTTP_200_OK: {"description": "All systems operational and database connected"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Service degraded or database unreachable"},
    },
)
def get_health(
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Perform real-time diagnostics verifying app status and database responsiveness."""
    db_connected = False
    db_details = None

    try:
        # Actually execute a lightweight query to verify connectivity
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception as exc:
        db_connected = False
        db_details = "Database connection query failed."
        logger.warning(f"Health check database query failure: {exc}")

    if db_connected:
        overall_status = "healthy"
        response.status_code = status.HTTP_200_OK
    else:
        overall_status = "degraded"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        database=DatabaseHealthInfo(
            status="connected" if db_connected else "disconnected",
            details=db_details,
        ),
    )
