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
    ffmpeg_fingerprint: str = Field(
        default="deployment-unpinned",
        pattern=r"^(deployment-unpinned|sha256:[0-9a-f]{64})$",
    )
    media_validation_timeout_seconds: int = Field(default=30, ge=1, le=300)
    event_poll_interval_seconds: float = Field(default=0.5, ge=0.01, le=10)
    event_keepalive_seconds: float = Field(default=10, ge=0.05, le=60)
    event_stream_lifetime_seconds: float = Field(default=25, ge=0.05, le=300)
    event_batch_size: int = Field(default=100, ge=1, le=1000)

    @field_validator("data_root")
    @classmethod
    def require_absolute_data_root(cls, data_root: Path) -> Path:
        if not data_root.is_absolute():
            raise ValueError("data root must be an absolute path")
        return data_root
