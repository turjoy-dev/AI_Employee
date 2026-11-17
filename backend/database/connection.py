"""Database connection management, engine lifecycle, and session dependency."""

import os
import sqlite3
from typing import Generator, Tuple, Optional
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection: object, _connection_record: object) -> None:
    """Enable foreign keys and WAL concurrency mode on SQLite connections."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

def ensure_sqlite_directory(database_url: str) -> None:
    """Create the parent directory for a file-backed SQLite database URL if missing."""
    if not database_url.startswith("sqlite"):
        return
    db_path = make_url(database_url).database
    if not db_path or db_path == ":memory:":
        return
    db_dir = os.path.dirname(os.path.abspath(db_path))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)


# Configure engine arguments based on dialect
connect_args = {}
engine_kwargs = {
    "pool_pre_ping": True,
    "echo": settings.app_debug and settings.log_level.upper() == "DEBUG",
}
if settings.database_url.startswith("sqlite"):
    ensure_sqlite_directory(settings.database_url)
    connect_args["check_same_thread"] = False
    if ":memory:" in settings.database_url:
        engine_kwargs["poolclass"] = StaticPool

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    **engine_kwargs,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a managed database session."""
    session = SessionLocal()
    try:
        yield session
    except Exception as exc:
        logger.error(f"Database session error: {exc}", exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


def check_db_connection() -> Tuple[bool, Optional[str]]:
    """Verify live connectivity to the configured database.
    
    Returns:
        Tuple[bool, Optional[str]]: (is_healthy, error_message)
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        error_msg = f"Database health check failed: {str(exc)}"
        logger.warning(error_msg)
        return False, str(exc)


def dispose_engine() -> None:
    """Safely dispose of connection pools on application shutdown."""
    logger.info("Disposing database engine connection pool.")
    if ":memory:" not in str(engine.url):
        engine.dispose()
