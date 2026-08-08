"""Versioned JSON-lines protocol between a worker supervisor and one child."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter
from veridash_core import ErrorKind

PROTOCOL_VERSION = 1


class ChildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal[1] = PROTOCOL_VERSION
    module_id: str
    implementation_version: str
    attempt_number: int = Field(ge=1)
    parameters: dict[str, JsonValue]


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
    outputs: dict[str, JsonValue]


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
