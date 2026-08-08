import pytest
from pydantic import BaseModel
from veridash_analysis import (
    AnalysisRegistry,
    ImplementationFingerprint,
    InvalidAnalysisGraphError,
    ModuleManifest,
    analysis_cache_key,
    manifest_hash,
)
from veridash_core import ResourceClass


class ExampleParameters(BaseModel):
    interval_seconds: float
    include_scenes: bool = True


def manifest(
    module_id: str,
    *,
    dependencies: tuple[str, ...] = (),
    automatic: bool = True,
    version: str = "1.0.0",
) -> ModuleManifest:
    return ModuleManifest(
        module_id=module_id,
        display_name=module_id.replace("_", " ").title(),
        version=version,
        result_schema_version=1,
        resource_class=ResourceClass.CPU,
        dependencies=dependencies,
        automatic=automatic,
        fingerprints=(ImplementationFingerprint(name="ffmpeg", value="7.1.1"),),
    )


def test_registry_returns_a_dependency_first_automatic_plan() -> None:
    registry = AnalysisRegistry(
        [
            manifest("stitch_frames", dependencies=("extract_keyframes",), automatic=False),
            manifest("detect_objects", dependencies=("extract_keyframes",)),
            manifest("extract_keyframes"),
            manifest("probe_media"),
        ]
    )

    assert [item.module_id for item in registry.automatic_plan()] == [
        "extract_keyframes",
        "detect_objects",
        "probe_media",
    ]


@pytest.mark.parametrize(
    "manifests",
    [
        [manifest("probe_media"), manifest("probe_media", version="2.0.0")],
        [manifest("coordinates", dependencies=("missing",))],
        [
            manifest("first", dependencies=("second",)),
            manifest("second", dependencies=("first",)),
        ],
        [
            manifest("manual", automatic=False),
            manifest("automatic", dependencies=("manual",)),
        ],
    ],
)
def test_registry_rejects_ambiguous_or_invalid_graphs(
    manifests: list[ModuleManifest],
) -> None:
    with pytest.raises(InvalidAnalysisGraphError):
        AnalysisRegistry(manifests)


def test_cache_key_covers_manifest_parameters_source_and_named_outputs() -> None:
    current_manifest = manifest("detect_objects", dependencies=("extract_keyframes",))
    parameters = ExampleParameters(interval_seconds=1.0)
    source_hash = "a" * 64
    outputs = {
        "extract_keyframes": {
            "frames": "b" * 64,
            "index": "c" * 64,
        }
    }
    first = analysis_cache_key(
        current_manifest,
        source_sha256=source_hash,
        parameters=parameters,
        dependency_artifact_hashes=outputs,
    )
    reordered = analysis_cache_key(
        current_manifest,
        source_sha256=source_hash,
        parameters=parameters,
        dependency_artifact_hashes={
            "extract_keyframes": {
                "index": "c" * 64,
                "frames": "b" * 64,
            }
        },
    )

    assert first == reordered
    assert first != analysis_cache_key(
        current_manifest,
        source_sha256=source_hash,
        parameters=ExampleParameters(interval_seconds=2.0),
        dependency_artifact_hashes=outputs,
    )
    assert manifest_hash(current_manifest) != manifest_hash(
        manifest(
            "detect_objects",
            dependencies=("extract_keyframes",),
            version="2.0.0",
        )
    )


def test_cache_key_requires_every_declared_dependency() -> None:
    with pytest.raises(ValueError, match="must match"):
        analysis_cache_key(
            manifest("detect_objects", dependencies=("extract_keyframes",)),
            source_sha256="a" * 64,
            parameters=ExampleParameters(interval_seconds=1.0),
            dependency_artifact_hashes={},
        )
