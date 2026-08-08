import pytest
from veridash_core.jobs import (
    TERMINAL_JOB_STATES,
    ArtifactKind,
    AttemptState,
    ErrorKind,
    JobState,
    can_transition_job,
    require_job_transition,
)
from veridash_core.resources import ResourceClass, default_concurrency


def test_domain_enums_are_wire_values() -> None:
    assert JobState.WAITING_FOR_DEPENDENCIES == "waiting_for_dependencies"
    assert ErrorKind.INVALID_INPUT == "invalid_input"
    assert AttemptState.LOST == "lost"
    assert ArtifactKind.JSON == "json"


def test_gpu_default_matches_single_vps_capacity() -> None:
    assert default_concurrency(ResourceClass.GPU) == 2


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (JobState.WAITING_FOR_DEPENDENCIES, JobState.READY),
        (JobState.WAITING_FOR_DEPENDENCIES, JobState.BLOCKED),
        (JobState.READY, JobState.RUNNING),
        (JobState.RUNNING, JobState.RETRY_WAIT),
        (JobState.RUNNING, JobState.SUCCEEDED),
        (JobState.RETRY_WAIT, JobState.READY),
        (JobState.FAILED, JobState.READY),
        (JobState.BLOCKED, JobState.WAITING_FOR_DEPENDENCIES),
        (JobState.CANCELED, JobState.READY),
    ],
)
def test_valid_job_transitions(current: JobState, target: JobState) -> None:
    assert can_transition_job(current, target)
    require_job_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (JobState.WAITING_FOR_DEPENDENCIES, JobState.RUNNING),
        (JobState.READY, JobState.SUCCEEDED),
        (JobState.RETRY_WAIT, JobState.RUNNING),
        (JobState.SUCCEEDED, JobState.READY),
        (JobState.FAILED, JobState.SUCCEEDED),
    ],
)
def test_invalid_job_state_jumps_are_rejected(
    current: JobState,
    target: JobState,
) -> None:
    assert not can_transition_job(current, target)
    with pytest.raises(ValueError, match="invalid job transition"):
        require_job_transition(current, target)


def test_terminal_job_states_are_explicit() -> None:
    assert TERMINAL_JOB_STATES == {
        JobState.SUCCEEDED,
        JobState.FAILED,
        JobState.BLOCKED,
        JobState.CANCELED,
    }
