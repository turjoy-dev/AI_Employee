"""Application configuration management using Pydantic Settings."""

from functools import lru_cache
import os
from typing import List, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_FALLBACK_SECRET = "a9f8d7c6b5e4f3a2d1c0b9a8e7f6d5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application metadata
    app_name: str = "AI Employee"
    app_env: str = "development"
    app_debug: bool = True
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"

    # Server configuration
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    log_level: str = "INFO"

    # Database configuration
    database_url: str = "sqlite:///./ai_employee.db"

    # Security & JWT configuration
    secret_key: str = _DEV_FALLBACK_SECRET
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        """Reject insecure default JWT secret keys and wildcard CORS origins in production."""
        if self.app_env.strip().lower() == "production":
            if not self.secret_key or self.secret_key == _DEV_FALLBACK_SECRET:
                raise ValueError("A strong non-default SECRET_KEY must be set in production.")
            if "*" in self.allowed_origins:
                raise ValueError("Wildcard '*' CORS origins are forbidden in production.")
        return self

    @model_validator(mode="after")
    def disable_placeholder_langfuse_tracing(self) -> "Settings":
        """Disable OpenTelemetry Langfuse span export when placeholder credentials are present."""
        sk = (self.langfuse_secret_key or "").strip()
        pk = (self.langfuse_public_key or "").strip()
        if not sk or not pk or sk.startswith("sk-lf-your") or pk.startswith("pk-lf-your"):
            os.environ.setdefault("LANGFUSE_TRACING_ENABLED", "false")
        return self

    # LLM & Gemini / Ollama / Groq configuration
    llm_provider: str = "ollama"
    ollama_model: str = "gemma"
    ollama_base_url: str = "http://localhost:11434/v1"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Langfuse observability configuration
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # CORS configuration
    allowed_origins: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Union[str, List[str]]) -> List[str]:
        """Parse comma-separated origin strings into a list of strings."""
        if isinstance(value, str):
            # Split comma-separated values, strip whitespace, and filter out empties
            origins = [origin.strip() for origin in value.split(",") if origin.strip()]
            return origins if origins else ["http://localhost:3000", "http://127.0.0.1:3000"]
        return value


@lru_cache()
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()
