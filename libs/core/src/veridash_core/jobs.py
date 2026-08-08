"""Durable job and error classifications shared by all server processes."""

from enum import StrEnum


class JobState(StrEnum):
    """Logical analysis-job states persisted by the server."""

    WAITING_FOR_DEPENDENCIES = "waiting_for_dependencies"
    READY = "ready"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELED = "canceled"


class AttemptState(StrEnum):
    """One supervised execution's durable lifecycle."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    LOST = "lost"


class ErrorKind(StrEnum):
    """Stable failure categories that drive retry and UI behavior."""

    INVALID_INPUT = "invalid_input"
    DEPENDENCY_FAILED = "dependency_failed"
    TRANSIENT_INFRASTRUCTURE = "transient_infrastructure"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    WORKER_LOST = "worker_lost"
    STALLED = "stalled"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    CANCELED = "canceled"
    INTERNAL_BUG = "internal_bug"


TERMINAL_JOB_STATES = frozenset(
    {JobState.SUCCEEDED, JobState.FAILED, JobState.BLOCKED, JobState.CANCELED}
)

_ALLOWED_JOB_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.WAITING_FOR_DEPENDENCIES: frozenset(
        {JobState.READY, JobState.BLOCKED, JobState.CANCELED}
    ),
    JobState.READY: frozenset({JobState.RUNNING, JobState.CANCELED}),
    JobState.RUNNING: frozenset(
        {
            JobState.RETRY_WAIT,
            JobState.SUCCEEDED,
            JobState.FAILED,
            JobState.CANCELED,
        }
    ),
    JobState.RETRY_WAIT: frozenset({JobState.READY, JobState.FAILED, JobState.CANCELED}),
    JobState.FAILED: frozenset({JobState.READY}),
    JobState.BLOCKED: frozenset({JobState.WAITING_FOR_DEPENDENCIES}),
    JobState.CANCELED: frozenset({JobState.READY}),
    JobState.SUCCEEDED: frozenset(),
}


def can_transition_job(current: JobState, target: JobState) -> bool:
    """Return whether the explicit logical-job state edge is permitted."""
    return target in _ALLOWED_JOB_TRANSITIONS[current]


def require_job_transition(current: JobState, target: JobState) -> None:
    """Reject state jumps before a process attempts its guarded SQL update."""
    if not can_transition_job(current, target):
        raise ValueError(f"invalid job transition: {current} -> {target}")
