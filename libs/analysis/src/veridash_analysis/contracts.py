"""Lightweight analysis contracts safe to import outside worker images."""

from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field
from veridash_core.resources import ResourceClass


class ProgressStage(BaseModel):
    """A stable semantic stage a module may report while executing."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    stall_after_seconds: int | None = Field(default=None, gt=0)


class ModuleManifest(BaseModel):
    """Scheduler-visible metadata that imports no heavy analysis dependencies."""

    model_config = ConfigDict(frozen=True)

    module_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    version: str
    result_schema_version: int = Field(ge=1)
    resource_class: ResourceClass
    dependencies: tuple[str, ...] = ()
    automatic: bool = True
    progress_stages: tuple[ProgressStage, ...] = ()


class RunContext(Protocol):
    """Execution services supplied by the worker wrapper."""

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

    def run(
        self,
        context: RunContext,
        inputs: Mapping[str, Any],
        parameters: BaseModel,
    ) -> BaseModel: ...
