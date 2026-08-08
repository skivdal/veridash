"""Typed API configuration loaded only by the runnable application."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the HTTP API."""

    model_config = SettingsConfigDict(env_prefix="VERIDASH_", extra="ignore")

    database_url: str = "postgresql+asyncpg://veridash:veridash@127.0.0.1/veridash"
    session_cookie_name: str = "veridash_session"
    csrf_cookie_name: str = "veridash_csrf"
    session_cookie_secure: bool = True
    session_ttl_seconds: int = Field(default=60 * 60 * 24 * 30, ge=300, le=60 * 60 * 24 * 365)
    data_root: Path = Path("/var/lib/veridash")
    max_upload_bytes: int = Field(default=10 * 1024**3, ge=1024, le=1024**4)
    ffprobe_executable: str = "ffprobe"
    media_validation_timeout_seconds: int = Field(default=30, ge=1, le=300)

    @field_validator("data_root")
    @classmethod
    def require_absolute_data_root(cls, data_root: Path) -> Path:
        if not data_root.is_absolute():
            raise ValueError("data root must be an absolute path")
        return data_root
