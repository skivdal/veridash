import pytest
from pydantic import BaseModel
from veridash_analysis import (
    AnalysisRegistry,
    ImplementationFingerprint,
    InvalidAnalysisGraphError,
    ModuleManifest,
    OutputSpec,
    analysis_cache_key,
    analysis_request_key,
    manifest_hash,
)
from veridash_analysis.modules import production_manifests
from veridash_core import ArtifactKind, ResourceClass


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
        outputs=(
            OutputSpec(
                name="result",
                kind=ArtifactKind.JSON,
                media_type="application/json",
                schema_id=f"veridash.{module_id}",
                schema_version=1,
            ),
        ),
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
        [
            ModuleManifest(
                module_id="empty",
                display_name="Empty",
                version="1.0.0",
                result_schema_version=1,
                resource_class=ResourceClass.CPU,
            ),
            manifest("dependent", dependencies=("empty",)),
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


def test_request_identity_uses_dependency_requests_before_outputs_exist() -> None:
    current_manifest = manifest("detect_objects", dependencies=("extract_keyframes",))
    first = analysis_request_key(
        current_manifest,
        source_sha256="a" * 64,
        parameters=ExampleParameters(interval_seconds=1.0),
        dependency_request_keys={"extract_keyframes": "b" * 64},
    )

    assert first != analysis_request_key(
        current_manifest,
        source_sha256="a" * 64,
        parameters=ExampleParameters(interval_seconds=1.0),
        dependency_request_keys={"extract_keyframes": "c" * 64},
    )


def test_exact_media_tool_build_enables_cache_with_a_distinct_version() -> None:
    local = {item.module_id: item for item in production_manifests()}
    pinned = {
        item.module_id: item
        for item in production_manifests(ffmpeg_fingerprint=f"sha256:{'a' * 64}")
    }

    for module_id in ("probe_media", "extract_keyframes"):
        assert local[module_id].cacheable is False
        assert pinned[module_id].cacheable is True
        assert pinned[module_id].version == f"1.0.0+ffmpeg.{'a' * 64}"
        assert pinned[module_id].version != local[module_id].version
        assert any(item.value == f"sha256:{'a' * 64}" for item in pinned[module_id].fingerprints)


def test_invalid_media_tool_fingerprint_fails_closed() -> None:
    with pytest.raises(ValueError, match="FFmpeg fingerprint"):
        production_manifests(ffmpeg_fingerprint="ffmpeg-ish")
