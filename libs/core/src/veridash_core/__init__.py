"""Shared VeriDash domain types with no application side effects."""

from veridash_core.jobs import (
    TERMINAL_JOB_STATES,
    AttemptState,
    ErrorKind,
    JobState,
    can_transition_job,
    require_job_transition,
)
from veridash_core.resources import ResourceClass

__all__ = [
    "TERMINAL_JOB_STATES",
    "AttemptState",
    "ErrorKind",
    "JobState",
    "ResourceClass",
    "can_transition_job",
    "require_job_transition",
]
