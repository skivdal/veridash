import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from veridash_api.config import Settings
from veridash_api.main import create_app
from veridash_api.schema import (
    REQUIRED_DATABASE_SCHEMA_VERSION,
    DatabaseSchemaMismatchError,
    database_schema_is_current,
    require_current_database_schema,
)
from veridash_storage import FilesystemBlobStore


async def test_health() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "veridash-api"}


@pytest.mark.db
async def test_readiness_checks_runtime_dependencies(tmp_path: Path) -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_async_engine(database_url)
    app = create_app(
        settings=Settings(database_url=database_url, session_cookie_secure=False),
        database_engine=engine,
        blob_store=FilesystemBlobStore(tmp_path / "data"),
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/ready")
    finally:
        await engine.dispose()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "veridash-api",
        "dependencies": {
            "database": "ready",
            "database_schema": "ready",
            "blob_storage": "ready",
            "ffprobe": "ready",
        },
    }


@pytest.mark.db
async def test_readiness_returns_503_when_storage_is_unavailable(tmp_path: Path) -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    class UnavailableBlobStore(FilesystemBlobStore):
        def check_ready(self) -> None:
            raise OSError("test storage outage")

    engine = create_async_engine(database_url)
    app = create_app(
        settings=Settings(database_url=database_url, session_cookie_secure=False),
        database_engine=engine,
        blob_store=UnavailableBlobStore(tmp_path / "data"),
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/ready")
    finally:
        await engine.dispose()

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert response.json()["dependencies"] == {
        "database": "ready",
        "database_schema": "ready",
        "blob_storage": "unavailable",
        "ffprobe": "ready",
    }


def test_required_schema_version_tracks_latest_migration() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    latest_migration = max(
        (repository_root / "db" / "migrations").glob("*.sql"),
        key=lambda path: path.name,
    )

    assert latest_migration.name.startswith(f"{REQUIRED_DATABASE_SCHEMA_VERSION}_")


@pytest.mark.db
async def test_database_schema_guard_rejects_a_pending_migration() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(
                    text("DELETE FROM schema_migrations WHERE version = :version"),
                    {"version": REQUIRED_DATABASE_SCHEMA_VERSION},
                )
                assert not await database_schema_is_current(connection)
                with pytest.raises(DatabaseSchemaMismatchError, match="db:up"):
                    await require_current_database_schema(connection)
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
