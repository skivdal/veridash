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
