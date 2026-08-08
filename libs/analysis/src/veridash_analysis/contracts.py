"""Lightweight analysis contracts safe to import outside worker images."""

from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from veridash_core import ArtifactKind, ResourceClass


class ProgressStage(BaseModel):
    """A stable semantic stage a module may report while executing."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    stall_after_seconds: int | None = Field(default=None, gt=0)


class ImplementationFingerprint(BaseModel):
    """A named tool, model, prompt, or provider revision affecting output."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$", max_length=100)
    value: str = Field(min_length=1, max_length=500)


class OutputSpec(BaseModel):
    """One required named artifact published by a successful module."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=100)
    kind: ArtifactKind
    media_type: str = Field(min_length=1, max_length=255)
    schema_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$", max_length=200)
    schema_version: int = Field(ge=1)


class ModuleManifest(BaseModel):
    """Scheduler-visible metadata that imports no heavy analysis dependencies."""

    model_config = ConfigDict(frozen=True)

    module_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=100)
    result_schema_version: int = Field(ge=1)
    resource_class: ResourceClass
    dependencies: tuple[str, ...] = ()
    default_parameters: dict[str, JsonValue] = Field(default_factory=dict)
    automatic: bool = True
    max_attempts: int = Field(default=3, ge=1, le=100)
    priority: int = Field(default=0, ge=-32768, le=32767)
    cacheable: bool = True
    fingerprints: tuple[ImplementationFingerprint, ...] = ()
    progress_stages: tuple[ProgressStage, ...] = ()
    outputs: tuple[OutputSpec, ...] = ()

    @model_validator(mode="after")
    def validate_named_members(self) -> "ModuleManifest":
        if self.module_id in self.dependencies:
            raise ValueError("an analysis module cannot depend on itself")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("analysis dependencies must be unique")
        if len({item.key for item in self.progress_stages}) != len(self.progress_stages):
            raise ValueError("progress stage keys must be unique")
        if len({item.name for item in self.fingerprints}) != len(self.fingerprints):
            raise ValueError("implementation fingerprint names must be unique")
        if len({item.name for item in self.outputs}) != len(self.outputs):
            raise ValueError("analysis output names must be unique")
        return self


class RunContext(Protocol):
    """Execution services supplied by the worker wrapper."""

    @property
    def attempt_number(self) -> int: ...

    def heartbeat(self) -> None: ...

    def report_progress(
        self,
        *,
        stage: str,
        completed: int | None = None,
        total: int | None = None,
        message: str | None = None,
    ) -> None: ...

    def is_canceled(self) -> bool: ...


class AnalysisModule(Protocol):
    """Interface implemented by independently testable analysis kernels."""

    manifest: ModuleManifest
    parameter_model: type[BaseModel]

    def run(
        self,
        context: RunContext,
        inputs: Mapping[str, Any],
        parameters: BaseModel,
    ) -> BaseModel: ...
