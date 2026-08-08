"""Validated lightweight module registry and deterministic analysis identities."""

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from types import MappingProxyType

from pydantic import BaseModel

from veridash_analysis.contracts import ModuleManifest

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class InvalidAnalysisGraphError(ValueError):
    """Registered manifests do not form a usable dependency graph."""


class AnalysisRegistry:
    """One immutable, cycle-free set of active module manifests."""

    def __init__(self, manifests: Iterable[ModuleManifest]) -> None:
        by_id: dict[str, ModuleManifest] = {}
        for manifest in manifests:
            if manifest.module_id in by_id:
                raise InvalidAnalysisGraphError(f"duplicate analysis module: {manifest.module_id}")
            by_id[manifest.module_id] = manifest
        self._by_id = MappingProxyType(by_id)
        self._ordered = _topological_order(self._by_id)
        for manifest in self._ordered:
            if not manifest.automatic:
                continue
            unavailable = [
                dependency
                for dependency in manifest.dependencies
                if not self._by_id[dependency].automatic
            ]
            if unavailable:
                names = ", ".join(unavailable)
                raise InvalidAnalysisGraphError(
                    f"automatic module {manifest.module_id} depends on non-automatic: {names}"
                )

    @property
    def manifests(self) -> tuple[ModuleManifest, ...]:
        return self._ordered

    def automatic_plan(self) -> tuple[ModuleManifest, ...]:
        """Return dependency-first automatic modules for DAG creation."""
        return tuple(manifest for manifest in self._ordered if manifest.automatic)

    def get(self, module_id: str) -> ModuleManifest:
        try:
            return self._by_id[module_id]
        except KeyError as exception:
            raise KeyError(f"unknown analysis module: {module_id}") from exception


def manifest_document(manifest: ModuleManifest) -> str:
    """Return the canonical JSON persisted with a versioned definition."""
    return _canonical_json(manifest.model_dump(mode="json"))


def manifest_hash(manifest: ModuleManifest) -> str:
    return hashlib.sha256(manifest_document(manifest).encode()).hexdigest()


def analysis_cache_key(
    manifest: ModuleManifest,
    *,
    source_sha256: str,
    parameters: BaseModel,
    dependency_artifact_hashes: Mapping[str, Mapping[str, str]],
) -> str:
    """Hash every declared output-affecting input into a server-owned identity."""
    _require_sha256(source_sha256, label="source")
    expected_dependencies = set(manifest.dependencies)
    if set(dependency_artifact_hashes) != expected_dependencies:
        raise ValueError("dependency artifact hashes must match the module manifest")
    normalized_dependencies: dict[str, dict[str, str]] = {}
    for dependency, outputs in dependency_artifact_hashes.items():
        if not outputs:
            raise ValueError(f"dependency {dependency} has no output artifact hashes")
        normalized_outputs: dict[str, str] = {}
        for output_name, artifact_hash in outputs.items():
            _require_sha256(artifact_hash, label=f"dependency {dependency}")
            normalized_outputs[output_name] = artifact_hash
        normalized_dependencies[dependency] = normalized_outputs

    identity = {
        "manifest_hash": manifest_hash(manifest),
        "source_sha256": source_sha256,
        "parameters": parameters.model_dump(mode="json"),
        "dependency_artifact_hashes": normalized_dependencies,
    }
    return hashlib.sha256(_canonical_json(identity).encode()).hexdigest()


def _topological_order(
    manifests: Mapping[str, ModuleManifest],
) -> tuple[ModuleManifest, ...]:
    ordered: list[ModuleManifest] = []
    complete: set[str] = set()
    visiting: list[str] = []

    def visit(module_id: str) -> None:
        if module_id in complete:
            return
        if module_id in visiting:
            cycle_start = visiting.index(module_id)
            cycle = " -> ".join([*visiting[cycle_start:], module_id])
            raise InvalidAnalysisGraphError(f"analysis dependency cycle: {cycle}")
        manifest = manifests.get(module_id)
        if manifest is None:
            parent = visiting[-1] if visiting else "registry"
            raise InvalidAnalysisGraphError(
                f"analysis module {parent} has unknown dependency: {module_id}"
            )
        visiting.append(module_id)
        for dependency in manifest.dependencies:
            visit(dependency)
        visiting.pop()
        complete.add(module_id)
        ordered.append(manifest)

    for module_id in sorted(manifests):
        visit(module_id)
    return tuple(ordered)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _require_sha256(value: str, *, label: str) -> None:
    if SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} identity is not a SHA-256 hash")
