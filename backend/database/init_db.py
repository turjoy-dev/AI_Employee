"""Database schema initialization and initial seeding."""

from typing import Optional
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.connection import engine as default_engine
from backend.database.models import Base, SystemMetadata

logger = get_logger(__name__)


def init_db(target_engine: Optional[Engine] = None) -> None:
    """Create all database tables defined in SQLAlchemy models if they do not exist."""
    active_engine = target_engine or default_engine
    logger.info("Initializing database schema...")
    try:
        Base.metadata.create_all(bind=active_engine)
        logger.info("Database tables verified successfully.")

        # Seed or update basic metadata using SQLAlchemy 2.0 select()
        with Session(active_engine) as session:
            settings = get_settings()
            stmt = select(SystemMetadata).where(SystemMetadata.key == "initialized_version")
            metadata_record = session.execute(stmt).scalar_one_or_none()
            if not metadata_record:
                metadata_record = SystemMetadata(
                    key="initialized_version",
                    value=settings.app_version,
                )
                session.add(metadata_record)
                session.commit()
                logger.info(f"SystemMetadata initialized with version {settings.app_version}.")
    except Exception as exc:
        logger.error(f"Error during database initialization: {exc}", exc_info=True)
        raise
