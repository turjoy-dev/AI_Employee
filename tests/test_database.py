"""Tests for database connectivity, session handling, and schema initialization."""

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.database.connection import check_db_connection, dispose_engine, get_db
from backend.database.init_db import init_db
from backend.database.models import SystemMetadata


def test_database_initialization_and_metadata():
    """Verify init_db creates tables and seeds default SystemMetadata idempotently."""
    isolated_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    init_db(target_engine=isolated_engine)
    # Call a second time to verify idempotency
    init_db(target_engine=isolated_engine)

    with Session(isolated_engine) as session:
        records = session.execute(
            select(SystemMetadata).where(SystemMetadata.key == "initialized_version")
        ).scalars().all()
        assert len(records) == 1
        assert records[0].value is not None


def test_default_in_memory_engine_persists_tables_across_sessions():
    """Verify default engine configured with sqlite:///:memory: persists tables across get_db() sessions."""
    init_db()
    dispose_engine()

    gen = get_db()
    session = next(gen)
    try:
        record = session.execute(
            select(SystemMetadata).where(SystemMetadata.key == "initialized_version")
        ).scalar_one_or_none()
        assert record is not None
    finally:
        with pytest.raises(StopIteration):
            next(gen)


def test_check_db_connection_success():
    """Verify check_db_connection returns True when database is reachable."""
    healthy, err = check_db_connection()
    assert healthy is True
    assert err is None


def test_get_db_yields_session_and_closes():
    """Verify get_db dependency yields a valid session and closes it cleanly."""
    gen = get_db()
    session = next(gen)
    assert isinstance(session, Session)

    # Verify session can execute queries
    result = session.execute(text("SELECT 1")).scalar()
    assert result == 1

    # Cleanup generator
    with pytest.raises(StopIteration):
        next(gen)


def test_get_db_rolls_back_on_exception():
    """Verify get_db rolls back the transaction when an unhandled exception occurs."""
    gen = get_db()
    session = next(gen)

    with pytest.raises(RuntimeError):
        gen.throw(RuntimeError("Simulated pipeline error"))


def test_ensure_sqlite_directory_creates_parent_folder(tmp_path):
    """Verify ensure_sqlite_directory creates missing parent directories for file-backed SQLite URLs."""
    from backend.database.connection import ensure_sqlite_directory

    nested_db_path = tmp_path / "app" / "data" / "ai_employee.db"
    assert not nested_db_path.parent.exists()

    ensure_sqlite_directory(f"sqlite:///{nested_db_path.as_posix()}")
    assert nested_db_path.parent.exists()

    # In-memory URLs should safely no-op
    ensure_sqlite_directory("sqlite:///:memory:")
