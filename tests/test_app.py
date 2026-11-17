"""Tests for application startup, root metadata endpoint, CORS, and global error handling."""

from fastapi import status
from fastapi.testclient import TestClient
from backend.main import create_app


def test_root_endpoint(client: TestClient):
    """Test that GET / returns the basic application metadata and links."""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["name"] == "AI Employee"
    assert data["version"] == "0.1.0"
    assert data["environment"] in ["testing", "development"]
    assert data["docs_url"] == "/docs"
    assert data["health_check"] == "/api/v1/health"


def test_root_openapi_schema_has_typed_response_model(client: TestClient):
    """Test that OpenAPI schema defines a formal RootResponse model for GET / instead of untyped dict."""
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK

    openapi = response.json()
    schemas = openapi.get("components", {}).get("schemas", {})
    assert "RootResponse" in schemas
    required_fields = set(schemas["RootResponse"].get("required", []))
    assert {"name", "version", "environment", "docs_url", "health_check"}.issubset(required_fields)


def test_cors_headers(client: TestClient):
    """Test that configured CORS origins are respected."""
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/v1/health", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_global_error_handler():
    """Test that unhandled exceptions are caught and sanitized by the global error handler."""
    app = create_app()

    @app.get("/test-internal-error")
    def trigger_error():
        raise ValueError("Sensitive internal secret that should not leak to client")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/test-internal-error")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        data = response.json()
        assert data["error"] == "Internal Server Error"
        # Verify secret message is not exposed
        assert "Sensitive internal secret" not in response.text
