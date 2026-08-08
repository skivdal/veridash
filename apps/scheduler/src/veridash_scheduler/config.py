"""Typed scheduler process configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VERIDASH_SCHEDULER_", extra="ignore")

    database_url: str = "postgresql+asyncpg://veridash:veridash@127.0.0.1/veridash"
    poll_interval_seconds: float = Field(default=1.0, ge=0.1, le=60)
    batch_size: int = Field(default=100, ge=1, le=1000)
    worker_lost_retry_delay_seconds: int = Field(default=10, ge=0, le=3600)
