import pytest
from pydantic import ValidationError
from veridash_analysis import ModuleManifest, ProgressStage
from veridash_core.resources import ResourceClass


def test_manifest_is_lightweight_and_frozen() -> None:
    manifest = ModuleManifest(
        module_id="probe_media",
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
            version="1.0.0",
            result_schema_version=1,
            resource_class=ResourceClass.CPU,
        )
