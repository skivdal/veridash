"""Authenticated project lifecycle against a real migrated PostgreSQL database."""

import os
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Cookies
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from veridash_analysis import AnalysisRegistry, ModuleManifest, OutputSpec
from veridash_api.auth.passwords import hash_password
from veridash_api.config import Settings
from veridash_api.main import create_app
from veridash_core import ArtifactKind, ResourceClass
from veridash_storage import FilesystemBlobStore


async def _create_test_user(engine: AsyncEngine, username: str, password: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO app_user (username, password_hash)
                VALUES (:username, :password_hash)
                """
            ),
            {"username": username, "password_hash": hash_password(password)},
        )


async def _create_test_project(engine: AsyncEngine, username: str) -> str:
    project_id = uuid4()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO project (id, user_id, title)
                SELECT :project_id, id, 'Another user project'
                FROM app_user
                WHERE username = :username
                """
            ),
            {"project_id": project_id, "username": username},
        )
    return str(project_id)


async def _delete_test_users(engine: AsyncEngine, usernames: list[str]) -> None:
    async with engine.begin() as connection:
        project_filter = """
            SELECT project.id
            FROM project
            JOIN app_user ON app_user.id = project.user_id
            WHERE app_user.username = ANY(:usernames)
        """
        for table in (
            "project_event",
            "project_analysis_result",
            "analysis_job_attempt",
            "analysis_job_dependency",
            "analysis_job",
        ):
            await connection.execute(
                text(f"DELETE FROM {table} WHERE project_id IN ({project_filter})"),
                {"usernames": usernames},
            )
        await connection.execute(
            text(
                """
                DELETE FROM analysis_definition
                WHERE module_id IN ('test_probe', 'test_derived')
                """
            )
        )
        await connection.execute(
            text(
                """
                DELETE FROM source_media
                WHERE project_id IN (
                    SELECT project.id
                    FROM project
                    JOIN app_user ON app_user.id = project.user_id
                    WHERE app_user.username = ANY(:usernames)
                )
                """
            ),
            {"usernames": usernames},
        )
        await connection.execute(
            text(
                """
                DELETE FROM project
                WHERE user_id IN (SELECT id FROM app_user WHERE username = ANY(:usernames))
                """
            ),
            {"usernames": usernames},
        )
        await connection.execute(
            text("DELETE FROM app_user WHERE username = ANY(:usernames)"),
            {"usernames": usernames},
        )


async def _clear_test_throttle(engine: AsyncEngine, remote_address: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM login_throttle WHERE remote_address = :remote_address"),
            {"remote_address": remote_address},
        )


def _create_tiny_video(path: Path) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg is required for media ingestion integration tests")
    subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=16x16:d=0.2",
            "-an",
            "-c:v",
            "mpeg4",
            "-y",
            str(path),
        ],
        check=True,
    )
    return path.read_bytes()


@pytest.mark.db
async def test_session_project_and_media_lifecycle_survives_api_restart(
    tmp_path: Path,
) -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    suffix = uuid4().hex
    username = f"api-test-{suffix}"
    other_username = f"api-test-other-{suffix}"
    password = "correct horse battery staple"
    engine = create_async_engine(database_url)
    settings = Settings(database_url=database_url, session_cookie_secure=False)
    store = FilesystemBlobStore(tmp_path / "data")
    analysis_registry = AnalysisRegistry(
        (
            ModuleManifest(
                module_id="test_probe",
                display_name="Test probe",
                version="1.0.0",
                result_schema_version=1,
                resource_class=ResourceClass.CPU,
                outputs=(
                    OutputSpec(
                        name="result",
                        kind=ArtifactKind.JSON,
                        media_type="application/json",
                        schema_id="veridash.test_probe",
                        schema_version=1,
                    ),
                ),
            ),
            ModuleManifest(
                module_id="test_derived",
                display_name="Test derived analysis",
                version="1.0.0",
                result_schema_version=1,
                resource_class=ResourceClass.CPU,
                dependencies=("test_probe",),
                default_parameters={"threshold": 0.5},
            ),
        )
    )
    video_bytes = _create_tiny_video(tmp_path / "source.mp4")
    remote_address = "198.51.100.10"
    await _create_test_user(engine, username, password)
    await _create_test_user(engine, other_username, password)
    other_project_id = await _create_test_project(engine, other_username)

    try:
        app = create_app(
            settings=settings,
            database_engine=engine,
            blob_store=store,
            analysis_registry=analysis_registry,
        )
        async with AsyncClient(
            transport=ASGITransport(app=app, client=(remote_address, 123)),
            base_url="http://test",
        ) as client:
            unauthenticated = await client.get("/api/projects")
            assert unauthenticated.status_code == 401
            assert unauthenticated.json()["code"] == "authentication_required"

            invalid_login = await client.post(
                "/api/auth/login",
                json={"username": username, "password": "incorrect"},
            )
            assert invalid_login.status_code == 401
            assert invalid_login.json()["code"] == "invalid_credentials"

            login = await client.post(
                "/api/auth/login",
                json={"username": f"  {username.upper()}  ", "password": password},
            )
            assert login.status_code == 200
            assert login.json()["user"]["username"] == username
            assert "HttpOnly" in login.headers.get_list("set-cookie")[0]

            rejected_create = await client.post(
                "/api/projects",
                json={"title": "First investigation"},
            )
            assert rejected_create.status_code == 403
            assert rejected_create.json()["code"] == "csrf_check_failed"

            csrf_token = client.cookies.get(settings.csrf_cookie_name)
            assert csrf_token is not None
            create = await client.post(
                "/api/projects",
                json={"title": "  First investigation  "},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert create.status_code == 201
            project = create.json()
            assert project["title"] == "First investigation"
            assert project["state"] == "active"

            invalid_create = await client.post(
                "/api/projects",
                json={"title": "   "},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert invalid_create.status_code == 422
            assert invalid_create.json()["code"] == "invalid_request"

            projects = await client.get("/api/projects")
            assert projects.status_code == 200
            assert [item["id"] for item in projects.json()] == [project["id"]]

            project_detail = await client.get(f"/api/projects/{project['id']}")
            assert project_detail.status_code == 200
            assert project_detail.json() == project

            rejected_rename = await client.patch(
                f"/api/projects/{project['id']}",
                json={"title": "Renamed investigation"},
            )
            assert rejected_rename.status_code == 403

            rename = await client.patch(
                f"/api/projects/{project['id']}",
                json={"title": "  Renamed investigation  "},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert rename.status_code == 200
            project = rename.json()
            assert project["title"] == "Renamed investigation"

            archive = await client.post(
                f"/api/projects/{project['id']}/archive",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert archive.status_code == 200
            project = archive.json()
            assert project["state"] == "archived"
            assert project["archived_at"] is not None

            archive_again = await client.post(
                f"/api/projects/{project['id']}/archive",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert archive_again.status_code == 200
            assert archive_again.json()["archived_at"] == project["archived_at"]
            assert archive_again.json()["updated_at"] == project["updated_at"]

            restore = await client.post(
                f"/api/projects/{project['id']}/restore",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert restore.status_code == 200
            project = restore.json()
            assert project["state"] == "active"
            assert project["archived_at"] is None

            missing = await client.get(f"/api/projects/{uuid4()}")
            assert missing.status_code == 404
            assert missing.json()["code"] == "project_not_found"

            unauthorized_project = await client.get(f"/api/projects/{other_project_id}")
            assert unauthorized_project.status_code == 404
            assert unauthorized_project.json()["code"] == "project_not_found"

            unauthorized_archive = await client.post(
                f"/api/projects/{other_project_id}/archive",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert unauthorized_archive.status_code == 404
            assert unauthorized_archive.json()["code"] == "project_not_found"

            reserve_media = await client.post(
                f"/api/projects/{project['id']}/media",
                json={"original_filename": "source.mp4"},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert reserve_media.status_code == 200
            media = reserve_media.json()
            assert media["upload_state"] == "pending"

            reserve_again = await client.post(
                f"/api/projects/{project['id']}/media",
                json={"original_filename": "different-name.mp4"},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert reserve_again.status_code == 200
            assert reserve_again.json()["id"] == media["id"]
            assert reserve_again.json()["original_filename"] == "different-name.mp4"

            invalid_content = await client.put(
                f"/api/uploads/{media['id']}/content",
                content=b"not a video",
                headers={
                    "Content-Type": "video/mp4",
                    "X-CSRF-Token": csrf_token,
                },
            )
            assert invalid_content.status_code == 200
            assert invalid_content.json()["size_bytes"] == len(b"not a video")

            invalid_complete = await client.post(
                f"/api/uploads/{media['id']}/complete",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert invalid_complete.status_code == 422
            assert invalid_complete.json()["code"] == "invalid_media"

            failed_media = await client.get(f"/api/projects/{project['id']}/media")
            assert failed_media.status_code == 200
            assert failed_media.json()["upload_state"] == "failed"

            upload_content = await client.put(
                f"/api/uploads/{media['id']}/content",
                content=video_bytes,
                headers={
                    "Content-Type": "text/plain",
                    "X-CSRF-Token": csrf_token,
                },
            )
            assert upload_content.status_code == 200
            assert upload_content.json()["upload_state"] == "pending"

            complete = await client.post(
                f"/api/uploads/{media['id']}/complete",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert complete.status_code == 200
            media = complete.json()
            assert media["upload_state"] == "uploaded"
            assert media["media_type"] == "video/mp4"
            assert media["size_bytes"] == len(video_bytes)

            analyses = await client.get(f"/api/projects/{project['id']}/analyses")
            assert analyses.status_code == 200
            assert {job["module_id"] for job in analyses.json()} == {
                "test_probe",
                "test_derived",
            }
            assert all(job["state"] == "waiting_for_dependencies" for job in analyses.json())

            complete_again = await client.post(
                f"/api/uploads/{media['id']}/complete",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert complete_again.status_code == 200
            analyses_again = await client.get(f"/api/projects/{project['id']}/analyses")
            assert len(analyses_again.json()) == 2

            unauthorized_analyses = await client.get(f"/api/projects/{other_project_id}/analyses")
            assert unauthorized_analyses.status_code == 404

            rejected_replacement = await client.put(
                f"/api/uploads/{media['id']}/content",
                content=video_bytes,
                headers={"X-CSRF-Token": csrf_token},
            )
            assert rejected_replacement.status_code == 409
            assert rejected_replacement.json()["code"] == "source_media_finalized"

            full_content = await client.get(f"/api/media/{media['id']}/content")
            assert full_content.status_code == 200
            assert full_content.content == video_bytes
            assert full_content.headers["Accept-Ranges"] == "bytes"

            ranged_content = await client.get(
                f"/api/media/{media['id']}/content",
                headers={"Range": "bytes=2-9"},
            )
            assert ranged_content.status_code == 206
            assert ranged_content.content == video_bytes[2:10]
            assert ranged_content.headers["Content-Range"] == (f"bytes 2-9/{len(video_bytes)}")

            invalid_range = await client.get(
                f"/api/media/{media['id']}/content",
                headers={"Range": f"bytes={len(video_bytes)}-"},
            )
            assert invalid_range.status_code == 416
            assert invalid_range.headers["Content-Range"] == f"bytes */{len(video_bytes)}"

            persisted_cookies = Cookies(client.cookies)

        restarted_app = create_app(
            settings=settings,
            database_engine=engine,
            blob_store=store,
            analysis_registry=analysis_registry,
        )
        async with AsyncClient(
            transport=ASGITransport(app=restarted_app, client=(remote_address, 124)),
            base_url="http://test",
            cookies=persisted_cookies,
        ) as restarted_client:
            current_user = await restarted_client.get("/api/auth/me")
            assert current_user.status_code == 200
            assert current_user.json()["user"]["username"] == username

            persisted_project = await restarted_client.get(f"/api/projects/{project['id']}")
            assert persisted_project.status_code == 200
            assert persisted_project.json()["title"] == "Renamed investigation"
            assert persisted_project.json()["state"] == "active"

            persisted_media = await restarted_client.get(f"/api/projects/{project['id']}/media")
            assert persisted_media.status_code == 200
            assert persisted_media.json()["sha256_hex"] == media["sha256_hex"]

            persisted_analyses = await restarted_client.get(
                f"/api/projects/{project['id']}/analyses"
            )
            assert persisted_analyses.status_code == 200
            assert len(persisted_analyses.json()) == 2

            persisted_range = await restarted_client.get(
                f"/api/media/{media['id']}/content",
                headers={"Range": "bytes=-5"},
            )
            assert persisted_range.status_code == 206
            assert persisted_range.content == video_bytes[-5:]

            csrf_token = restarted_client.cookies.get(settings.csrf_cookie_name)
            assert csrf_token is not None
            logout = await restarted_client.post(
                "/api/auth/logout",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert logout.status_code == 204

            logged_out = await restarted_client.get("/api/auth/me")
            assert logged_out.status_code == 401
    finally:
        await _delete_test_users(engine, [username, other_username])
        await _clear_test_throttle(engine, remote_address)
        await engine.dispose()


@pytest.mark.db
async def test_failed_logins_are_throttled_across_requests() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    username = f"api-throttle-test-{uuid4().hex}"
    password = "correct horse battery staple"
    remote_address = "198.51.100.11"
    engine = create_async_engine(database_url)
    settings = Settings(database_url=database_url, session_cookie_secure=False)
    await _create_test_user(engine, username, password)

    try:
        app = create_app(settings=settings, database_engine=engine)
        async with AsyncClient(
            transport=ASGITransport(app=app, client=(remote_address, 123)),
            base_url="http://test",
        ) as client:
            for _attempt in range(5):
                rejected = await client.post(
                    "/api/auth/login",
                    json={"username": username, "password": "incorrect"},
                )
                assert rejected.status_code == 401

            throttled = await client.post(
                "/api/auth/login",
                json={"username": username, "password": password},
            )
            assert throttled.status_code == 429
            assert throttled.json()["code"] == "login_throttled"
            assert throttled.headers["Retry-After"] == "900"
    finally:
        await _delete_test_users(engine, [username])
        await _clear_test_throttle(engine, remote_address)
        await engine.dispose()
