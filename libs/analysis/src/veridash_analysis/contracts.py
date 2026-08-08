"""Lightweight analysis contracts safe to import outside worker images."""

import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from veridash_core import ArtifactKind, ResourceClass

OUTPUT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,99}$")


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
    collection: bool = False
    minimum_items: int = Field(default=1, ge=0)

    @model_validator(mode="after")
    def validate_cardinality(self) -> "OutputSpec":
        if not self.collection and self.minimum_items != 1:
            raise ValueError("a scalar output must have exactly one item")
        return self


class JsonArtifactOutput(BaseModel):
    """One structured result returned by an analysis kernel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["json"] = "json"
    value: JsonValue


class BlobArtifactOutput(BaseModel):
    """One staged file returned for supervisor-owned immutable publication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["blob"] = "blob"
    path: Path


type ArtifactOutput = Annotated[
    JsonArtifactOutput | BlobArtifactOutput,
    Field(discriminator="type"),
]


class ModuleResult(BaseModel):
    """Named outputs from a successful analysis kernel invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outputs: dict[str, ArtifactOutput]


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
    requires_source_file: bool = False
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
        for collection in (item for item in self.outputs if item.collection):
            prefix = f"{collection.name}_"
            if any(item.name.startswith(prefix) for item in self.outputs):
                raise ValueError("collection output prefixes must not overlap output names")
        return self


class RunContext(Protocol):
    """Execution services supplied by the worker wrapper."""

    @property
    def attempt_number(self) -> int: ...

    @property
    def output_directory(self) -> Path: ...

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
    ) -> ModuleResult: ...


def resolve_output_specs(
    manifest: ModuleManifest,
    output_names: Iterable[str],
) -> dict[str, OutputSpec]:
    """Resolve concrete scalar/collection item names and enforce cardinality."""
    scalar_specs = {item.name: item for item in manifest.outputs if not item.collection}
    collection_specs = tuple(item for item in manifest.outputs if item.collection)
    resolved: dict[str, OutputSpec] = {}
    collection_counts = {item.name: 0 for item in collection_specs}
    for output_name in output_names:
        spec = match_output_spec(manifest, output_name)
        if spec.collection:
            collection_counts[spec.name] += 1
        if output_name in resolved:
            raise ValueError("analysis returned a duplicate output")
        resolved[output_name] = spec
    if not scalar_specs.keys() <= resolved.keys():
        raise ValueError("analysis did not return every required scalar output")
    for spec in collection_specs:
        if collection_counts[spec.name] < spec.minimum_items:
            raise ValueError("analysis collection has too few items")
    return resolved


def match_output_spec(manifest: ModuleManifest, output_name: str) -> OutputSpec:
    """Match one concrete output name without enforcing whole-result cardinality."""
    if OUTPUT_NAME_PATTERN.fullmatch(output_name) is None:
        raise ValueError("analysis output name has an invalid shape")
    scalar = next(
        (item for item in manifest.outputs if not item.collection and item.name == output_name),
        None,
    )
    if scalar is not None:
        return scalar
    matches = [
        item
        for item in manifest.outputs
        if item.collection and output_name.startswith(f"{item.name}_")
    ]
    if len(matches) != 1:
        raise ValueError("analysis returned an undeclared output")
    return matches[0]
