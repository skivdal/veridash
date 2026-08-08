"""Typed API configuration loaded only by the runnable application."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the HTTP API."""

    model_config = SettingsConfigDict(env_prefix="VERIDASH_", extra="ignore")

    database_url: str = "postgresql+asyncpg://veridash:veridash@127.0.0.1/veridash"
    session_cookie_name: str = "veridash_session"
    csrf_cookie_name: str = "veridash_csrf"
    session_cookie_secure: bool = True
    session_ttl_seconds: int = Field(default=60 * 60 * 24 * 30, ge=300, le=60 * 60 * 24 * 365)
