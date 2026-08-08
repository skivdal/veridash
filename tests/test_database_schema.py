"""Cross-process database constraints exercised against a migrated test database."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.db
async def test_project_accepts_only_one_source_video() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                result = await connection.execute(
                    text(
                        """
                        INSERT INTO app_user (username, password_hash)
                        VALUES (:username, :password_hash)
                        RETURNING id
                        """
                    ),
                    {
                        "username": "schema-test-user",
                        "password_hash": "not-a-real-password-hash",
                    },
                )
                user_id = result.scalar_one()
                project_id = uuid4()
                await connection.execute(
                    text(
                        """
                        INSERT INTO project (id, user_id, title)
                        VALUES (:id, :user_id, :title)
                        """
                    ),
                    {"id": project_id, "user_id": user_id, "title": "Schema constraint test"},
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO source_media (id, project_id, original_filename)
                        VALUES (:id, :project_id, :filename)
                        """
                    ),
                    {"id": uuid4(), "project_id": project_id, "filename": "first.mp4"},
                )

                with pytest.raises(IntegrityError):
                    async with connection.begin_nested():
                        await connection.execute(
                            text(
                                """
                    INSERT INTO source_media (id, project_id, original_filename)
                    VALUES (:id, :project_id, :filename)
                    """,
                            ),
                            {"id": uuid4(), "project_id": project_id, "filename": "second.mp4"},
                        )
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
