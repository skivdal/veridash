"""Administrator account management against a migrated PostgreSQL database."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from veridash_api.auth.passwords import hash_password
from veridash_api.config import Settings
from veridash_api.main import create_app
from veridash_storage import FilesystemBlobStore


async def _create_user(
    engine: AsyncEngine,
    *,
    username: str,
    email: str,
    password: str,
    is_admin: bool,
) -> int:
    async with engine.begin() as connection:
        result = await connection.execute(
            text(
                """
                INSERT INTO app_user (username, email, password_hash, is_admin)
                VALUES (:username, :email, :password_hash, :is_admin)
                RETURNING id
                """
            ),
            {
                "username": username,
                "email": email,
                "password_hash": hash_password(password),
                "is_admin": is_admin,
            },
        )
        return int(result.scalar_one())


async def _delete_users(engine: AsyncEngine, usernames: list[str]) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                DELETE FROM project
                WHERE user_id IN (
                    SELECT id FROM app_user WHERE username = ANY(:usernames)
                )
                """
            ),
            {"usernames": usernames},
        )
        await connection.execute(
            text("DELETE FROM app_user WHERE username = ANY(:usernames)"),
            {"usernames": usernames},
        )


@pytest.mark.db
async def test_admin_can_create_list_and_deactivate_users(tmp_path: Path) -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    suffix = uuid4().hex
    admin_username = f"admin-test-{suffix}"
    member_username = f"member-test-{suffix}"
    created_username = f"created-test-{suffix}"
    password = "correct horse battery staple"
    engine = create_async_engine(database_url)
    settings = Settings(database_url=database_url, session_cookie_secure=False)
    admin_id = await _create_user(
        engine,
        username=admin_username,
        email=f"{admin_username}@example.test",
        password=password,
        is_admin=True,
    )
    member_id = await _create_user(
        engine,
        username=member_username,
        email=f"{member_username}@example.test",
        password=password,
        is_admin=False,
    )
    async with engine.begin() as connection:
        for title in ("First member project", "Second member project"):
            await connection.execute(
                text(
                    """
                    INSERT INTO project (id, user_id, title)
                    VALUES (:id, :user_id, :title)
                    """
                ),
                {"id": uuid4(), "user_id": member_id, "title": title},
            )

    app = create_app(
        settings=settings,
        database_engine=engine,
        blob_store=FilesystemBlobStore(tmp_path / "data"),
    )
    try:
        async with (
            AsyncClient(
                transport=ASGITransport(app=app, client=("198.51.100.21", 123)),
                base_url="http://test",
            ) as admin_client,
            AsyncClient(
                transport=ASGITransport(app=app, client=("198.51.100.22", 123)),
                base_url="http://test",
            ) as member_client,
        ):
            admin_login = await admin_client.post(
                "/api/auth/login",
                json={"username": admin_username, "password": password},
            )
            assert admin_login.status_code == 200
            assert admin_login.json()["user"] == {
                "id": admin_id,
                "username": admin_username,
                "email": f"{admin_username}@example.test",
                "is_admin": True,
            }
            member_login = await member_client.post(
                "/api/auth/login",
                json={"username": member_username, "password": password},
            )
            assert member_login.status_code == 200

            forbidden = await member_client.get("/api/admin/users")
            assert forbidden.status_code == 403
            assert forbidden.json()["code"] == "admin_required"

            listed = await admin_client.get("/api/admin/users")
            assert listed.status_code == 200
            users = {user["username"]: user for user in listed.json()}
            assert users[admin_username]["last_login_at"] is not None
            assert users[member_username]["project_count"] == 2

            csrf_token = admin_client.cookies.get(settings.csrf_cookie_name)
            assert csrf_token is not None
            created = await admin_client.post(
                "/api/admin/users",
                json={
                    "username": f"  {created_username.upper()}  ",
                    "email": f"  {created_username.upper()}@EXAMPLE.TEST  ",
                    "password": password,
                },
                headers={"X-CSRF-Token": csrf_token},
            )
            assert created.status_code == 201
            assert created.json()["username"] == created_username
            assert created.json()["email"] == f"{created_username}@example.test"
            assert created.json()["is_admin"] is False
            assert created.json()["project_count"] == 0

            duplicate = await admin_client.post(
                "/api/admin/users",
                json={
                    "username": f"other-{suffix}",
                    "email": f"{created_username}@example.test",
                    "password": password,
                },
                headers={"X-CSRF-Token": csrf_token},
            )
            assert duplicate.status_code == 409
            assert duplicate.json()["code"] == "user_already_exists"

            protected_admin = await admin_client.post(
                f"/api/admin/users/{admin_id}/deactivate",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert protected_admin.status_code == 409

            deactivated = await admin_client.post(
                f"/api/admin/users/{member_id}/deactivate",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert deactivated.status_code == 200
            assert deactivated.json()["is_enabled"] is False

            revoked = await member_client.get("/api/auth/me")
            assert revoked.status_code == 401
    finally:
        await _delete_users(
            engine,
            [admin_username, member_username, created_username],
        )
        await engine.dispose()
