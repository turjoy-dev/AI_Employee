"""Pytest configuration, shared fixtures, and database test isolations."""

import os
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Enforce testing environment
os.environ["APP_ENV"] = "testing"
os.environ["APP_DEBUG"] = "false"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from backend.main import create_app
from backend.database.models import Base
from backend.database.connection import get_db

# Create an in-memory SQLite database specifically for test isolation
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all database schema tables once per test session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db_session(monkeypatch: pytest.MonkeyPatch) -> Generator[Session, None, None]:
    """Provide an isolated, rollbacked database session for individual tests."""
    import backend.database.connection as db_conn

    connection = test_engine.connect()
    transaction = connection.begin()
    TestSessionFactory = sessionmaker(
        bind=connection,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr(db_conn, "SessionLocal", TestSessionFactory)
    session = TestSessionFactory()

    yield session

    session.close()
    transaction.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        if table.name != "system_metadata":
            connection.execute(table.delete())
    connection.commit()
    connection.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient with the database dependency overridden."""
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
