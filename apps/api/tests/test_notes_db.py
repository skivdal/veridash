import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from veridash_api.errors import ApiProblem
from veridash_api.services.projects import get_project_note, save_project_note


@pytest.mark.db
async def test_project_notes_are_authorized_durable_and_revision_fenced() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            transaction = await connection.begin_nested()
            try:
                suffix = uuid4().hex
                users: list[int] = []
                for username in (f"note-owner-{suffix}", f"note-other-{suffix}"):
                    result = await connection.execute(
                        text(
                            """
                            INSERT INTO app_user (username, email, password_hash)
                            VALUES (:username, :email, 'not-a-real-password-hash')
                            RETURNING id
                            """
                        ),
                        {"username": username, "email": f"{username}@example.test"},
                    )
                    user_id = int(result.scalar_one())
                    users.append(user_id)
                project_id = uuid4()
                await connection.execute(
                    text(
                        """
                        INSERT INTO project (id, user_id, title)
                        VALUES (:id, :user_id, 'Note test')
                        """
                    ),
                    {"id": project_id, "user_id": users[0]},
                )

                empty = await get_project_note(
                    connection,
                    user_id=users[0],
                    project_id=project_id,
                )
                assert empty.body == ""
                assert empty.revision == 0

                first = await save_project_note(
                    connection,
                    user_id=users[0],
                    project_id=project_id,
                    body="First observation",
                    expected_revision=0,
                )
                assert first.revision == 1
                second = await save_project_note(
                    connection,
                    user_id=users[0],
                    project_id=project_id,
                    body="Revised observation",
                    expected_revision=1,
                )
                assert second.revision == 2

                with pytest.raises(ApiProblem) as stale:
                    await save_project_note(
                        connection,
                        user_id=users[0],
                        project_id=project_id,
                        body="Stale overwrite",
                        expected_revision=1,
                    )
                assert stale.value.status == 409
                assert (
                    await get_project_note(
                        connection,
                        user_id=users[0],
                        project_id=project_id,
                    )
                ).body == "Revised observation"

                with pytest.raises(ApiProblem) as hidden:
                    await get_project_note(
                        connection,
                        user_id=users[1],
                        project_id=project_id,
                    )
                assert hidden.value.status == 404
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
