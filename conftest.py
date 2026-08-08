"""Cross-suite safety boundaries for integration tests."""

import os

import pytest
from sqlalchemy.engine import make_url


def _database_identity(url: str) -> tuple[str | None, int | None, str | None, str | None]:
    parsed = make_url(url)
    return parsed.host, parsed.port, parsed.database, parsed.username


@pytest.fixture(autouse=True)
def prevent_database_tests_against_the_runtime_database() -> None:
    """Refuse a DB test URL that resolves to a configured application database."""
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url is None:
        return
    test_identity = _database_identity(test_url)
    runtime_urls = (
        os.environ.get("DATABASE_URL"),
        os.environ.get("VERIDASH_DATABASE_URL"),
        os.environ.get("VERIDASH_SCHEDULER_DATABASE_URL"),
        os.environ.get("VERIDASH_WORKER_DATABASE_URL"),
    )
    if any(
        _database_identity(runtime_url) == test_identity
        for runtime_url in runtime_urls
        if runtime_url is not None
    ):
        pytest.fail("TEST_DATABASE_URL must not identify a configured runtime database")
