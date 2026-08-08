import pytest
from pydantic import ValidationError
from veridash_analysis import ModuleManifest, OutputSpec, ProgressStage, resolve_output_specs
from veridash_core import ArtifactKind
from veridash_core.resources import ResourceClass


def test_manifest_is_lightweight_and_frozen() -> None:
    manifest = ModuleManifest(
        module_id="probe_media",
        display_name="Media metadata",
        version="1.0.0",
        result_schema_version=1,
        resource_class=ResourceClass.CPU,
        progress_stages=(ProgressStage(key="probing", label="Probing media"),),
    )

    assert manifest.automatic is True
    with pytest.raises(ValidationError):
        manifest.module_id = "changed"  # type: ignore[misc]


def test_manifest_rejects_display_names_as_ids() -> None:
    with pytest.raises(ValidationError):
        ModuleManifest(
            module_id="Probe Media",
            display_name="Media metadata",
            version="1.0.0",
            result_schema_version=1,
            resource_class=ResourceClass.CPU,
        )


def test_collection_outputs_resolve_concrete_names_and_cardinality() -> None:
    manifest = ModuleManifest(
        module_id="frames",
        display_name="Frames",
        version="1.0.0",
        result_schema_version=1,
        resource_class=ResourceClass.CPU,
        outputs=(
            OutputSpec(
                name="index",
                kind=ArtifactKind.JSON,
                media_type="application/json",
                schema_id="veridash.frames.index",
                schema_version=1,
            ),
            OutputSpec(
                name="frames",
                kind=ArtifactKind.BLOB,
                media_type="image/jpeg",
                schema_id="veridash.frame.jpeg",
                schema_version=1,
                collection=True,
            ),
        ),
    )

    resolved = resolve_output_specs(manifest, ("index", "frames_000001"))

    assert resolved["frames_000001"].name == "frames"
    with pytest.raises(ValueError, match="too few"):
        resolve_output_specs(manifest, ("index",))
    with pytest.raises(ValueError, match="undeclared"):
        resolve_output_specs(manifest, ("index", "preview"))
