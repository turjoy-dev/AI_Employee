"""Pydantic schemas for API health and diagnostics."""

from typing import Optional
from pydantic import BaseModel, Field


class DatabaseHealthInfo(BaseModel):
    """Detailed database connectivity information."""

    status: str = Field(..., description="Database connection status ('connected' or 'disconnected')")
    details: Optional[str] = Field(None, description="Diagnostic details or error message if disconnected")


class HealthResponse(BaseModel):
    """Health check endpoint response model."""

    status: str = Field(..., description="Overall service status ('healthy' or 'degraded')")
    app_name: str = Field(..., description="Configured application name")
    version: str = Field(..., description="Application semantic version")
    environment: str = Field(..., description="Runtime environment name")
    database: DatabaseHealthInfo = Field(..., description="Database health status")


class RootResponse(BaseModel):
    """Root endpoint response model with service metadata and navigation links."""

    name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application semantic version")
    environment: str = Field(..., description="Runtime environment")
    docs_url: str = Field(..., description="Interactive Swagger UI documentation path")
    health_check: str = Field(..., description="Health check API endpoint path")
