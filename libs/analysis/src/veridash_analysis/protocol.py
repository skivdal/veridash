"""Versioned JSON-lines protocol between a worker supervisor and one child."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter
from veridash_core import ErrorKind

from veridash_analysis.contracts import ArtifactOutput

PROTOCOL_VERSION = 2


class FileInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    media_type: str = Field(min_length=1, max_length=255)
    schema_id: str | None = None
    schema_version: int | None = Field(default=None, ge=1)


class JsonInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["json"] = "json"
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    media_type: str = Field(min_length=1, max_length=255)
    schema_id: str = Field(min_length=1, max_length=200)
    schema_version: int = Field(ge=1)
    value: JsonValue


type AnalysisInput = FileInput | JsonInput


class ChildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal[2] = PROTOCOL_VERSION
    module_id: str
    implementation_version: str
    ffmpeg_fingerprint: str = Field(
        default="deployment-unpinned",
        pattern=r"^(deployment-unpinned|sha256:[0-9a-f]{64})$",
    )
    attempt_number: int = Field(ge=1)
    output_directory: Path
    parameters: dict[str, JsonValue]
    inputs: dict[str, AnalysisInput] = Field(default_factory=dict)


class HeartbeatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["heartbeat"] = "heartbeat"


class ProgressMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["progress"] = "progress"
    stage: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=100)
    completed: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, gt=0)
    message: str | None = Field(default=None, max_length=1000)


class ResultMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["result"] = "result"
    outputs: dict[str, ArtifactOutput]


class ErrorMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["error"] = "error"
    error_kind: ErrorKind
    public_message: str = Field(min_length=1, max_length=1000)
    retryable: bool
    diagnostic: str | None = Field(default=None, max_length=10_000)


type ChildMessage = Annotated[
    HeartbeatMessage | ProgressMessage | ResultMessage | ErrorMessage,
    Field(discriminator="type"),
]
CHILD_MESSAGE_ADAPTER: TypeAdapter[ChildMessage] = TypeAdapter(ChildMessage)
