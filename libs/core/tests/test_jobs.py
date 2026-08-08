from veridash_core.jobs import ErrorKind, JobState
from veridash_core.resources import ResourceClass, default_concurrency


def test_domain_enums_are_wire_values() -> None:
    assert JobState.WAITING_FOR_DEPENDENCIES == "waiting_for_dependencies"
    assert ErrorKind.INVALID_INPUT == "invalid_input"


def test_gpu_default_matches_single_vps_capacity() -> None:
    assert default_concurrency(ResourceClass.GPU) == 2
