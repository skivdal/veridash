"""Typed worker-supervisor configuration."""

from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VERIDASH_WORKER_", extra="ignore")

    database_url: str = "postgresql+asyncpg://veridash:veridash@127.0.0.1/veridash"
    data_root: Path = Path("/var/lib/veridash")
    poll_interval_seconds: float = Field(default=1.0, ge=0.1, le=60)
    lease_seconds: int = Field(default=60, ge=5, le=3600)
    heartbeat_interval_seconds: float = Field(default=10, ge=0.1, le=300)
    startup_stall_seconds: float = Field(default=300, ge=1, le=86400)
    retry_delay_seconds: int = Field(default=10, ge=0, le=3600)
    max_protocol_line_bytes: int = Field(default=1024 * 1024, ge=1024, le=16 * 1024 * 1024)
    max_stderr_bytes: int = Field(default=64 * 1024, ge=1024, le=16 * 1024 * 1024)
    ffmpeg_fingerprint: str = Field(
        default="deployment-unpinned",
        pattern=r"^(deployment-unpinned|sha256:[0-9a-f]{64})$",
    )
    transcription_model_path: Path | None = None
    transcription_device: str = Field(default="auto", pattern=r"^(auto|cpu|cuda)$")
    transcription_compute_type: str = Field(
        default="default",
        pattern=r"^(default|float16|float32|int8|int8_float16|int8_float32)$",
    )
    openai_api_key: SecretStr | None = None

    @field_validator("data_root")
    @classmethod
    def require_absolute_data_root(cls, data_root: Path) -> Path:
        if not data_root.is_absolute():
            raise ValueError("data root must be an absolute path")
        return data_root

    @model_validator(mode="after")
    def validate_lease_cadence(self) -> "Settings":
        if self.heartbeat_interval_seconds >= self.lease_seconds:
            raise ValueError("heartbeat interval must be shorter than the attempt lease")
        return self

    @property
    def resolved_transcription_model_path(self) -> Path:
        return self.transcription_model_path or (
            self.data_root / "models" / "faster-whisper-medium"
        )
