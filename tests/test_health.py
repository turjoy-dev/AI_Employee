"""Tests for the system health check endpoint."""

from fastapi import status
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.database.connection import get_db


def test_health_check_success(client: TestClient):
    """Test that GET /api/v1/health returns 200 and healthy status when database is responsive."""
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "AI Employee"
    assert "version" in data
    assert data["environment"] in ["testing", "development"]
    assert data["database"]["status"] == "connected"
    assert data["database"]["details"] is None


def test_health_check_database_failure():
    """Test that GET /api/v1/health returns 503 and degraded status when database is unreachable."""
    app = create_app()

    def broken_get_db():
        class MockBrokenSession:
            def execute(self, *args, **kwargs):
                raise ConnectionError("Simulated database outage")

        yield MockBrokenSession()

    app.dependency_overrides[get_db] = broken_get_db

    with TestClient(app) as broken_client:
        response = broken_client.get("/api/v1/health")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"]["status"] == "disconnected"
        assert data["database"]["details"] == "Database connection query failed."

    app.dependency_overrides.clear()
