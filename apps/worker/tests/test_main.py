import pytest
from pydantic import ValidationError
from veridash_analysis import ProgressMessage
from veridash_analysis.synthetic import SyntheticAnalysisModule
from veridash_core import ResourceClass
from veridash_worker.config import Settings
from veridash_worker.main import validate_concurrency
from veridash_worker.supervisor import ProgressTracker, child_environment


def test_gpu_concurrency_may_be_two() -> None:
    assert validate_concurrency(ResourceClass.GPU, 2) == 2


def test_gpu_concurrency_cannot_exceed_two() -> None:
    with pytest.raises(SystemExit, match="cannot exceed"):
        validate_concurrency(ResourceClass.GPU, 3)


def test_heartbeat_must_renew_before_lease_expires() -> None:
    with pytest.raises(ValidationError, match="heartbeat interval"):
        Settings(lease_seconds=5, heartbeat_interval_seconds=5)


def test_child_environment_does_not_inherit_database_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://secret")
    monkeypatch.setenv("VERIDASH_WORKER_DATABASE_URL", "postgresql://also-secret")
    monkeypatch.setenv("PATH", "/usr/bin")

    environment = child_environment()

    assert environment["PATH"] == "/usr/bin"
    assert "DATABASE_URL" not in environment
    assert "VERIDASH_WORKER_DATABASE_URL" not in environment


def test_repeated_progress_does_not_hide_a_stalled_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = iter((0.0, 1.0, 29.0))
    monkeypatch.setattr("veridash_worker.supervisor.time.monotonic", lambda: next(clock))
    tracker = ProgressTracker.for_manifest(SyntheticAnalysisModule.manifest, 300)

    tracker.observe(ProgressMessage(stage="working", completed=1, total=2))

    assert tracker.remaining_seconds() == 2
