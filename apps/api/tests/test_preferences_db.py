import json
import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from veridash_api.errors import ApiProblem
from veridash_api.models import DASHBOARD_MODULE_IDS
from veridash_api.services.preferences import (
    get_dashboard_preference,
    save_dashboard_preference,
)


@pytest.mark.db
async def test_dashboard_preferences_are_durable_and_revision_fenced() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            transaction = await connection.begin_nested()
            try:
                user = await connection.execute(
                    text(
                        """
                        INSERT INTO app_user (username, email, password_hash)
                        VALUES (:username, :email, 'not-a-real-password-hash')
                        RETURNING id
                        """
                    ),
                    {
                        "username": f"dashboard-preference-{uuid4().hex}",
                        "email": f"dashboard-preference-{uuid4().hex}@example.test",
                    },
                )
                user_id = int(user.scalar_one())
                defaults = await get_dashboard_preference(connection, user_id=user_id)
                assert defaults.module_order == list(DASHBOARD_MODULE_IDS)
                assert defaults.hidden_modules == ["activity"]
                assert defaults.revision == 0

                reversed_order = [str(module_id) for module_id in reversed(DASHBOARD_MODULE_IDS)]
                saved = await save_dashboard_preference(
                    connection,
                    user_id=user_id,
                    module_order=reversed_order,
                    hidden_modules=["map"],
                    expected_revision=0,
                )
                assert saved.revision == 1
                assert saved.module_order == reversed_order
                assert saved.hidden_modules == ["map"]

                with pytest.raises(ApiProblem) as stale:
                    await save_dashboard_preference(
                        connection,
                        user_id=user_id,
                        module_order=[str(module_id) for module_id in DASHBOARD_MODULE_IDS],
                        hidden_modules=[],
                        expected_revision=0,
                    )
                assert stale.value.status == 409
                persisted = await get_dashboard_preference(connection, user_id=user_id)
                assert persisted.module_order == reversed_order
                assert persisted.hidden_modules == ["map"]

                legacy_order = [
                    module_id for module_id in DASHBOARD_MODULE_IDS if module_id != "activity"
                ]
                await connection.execute(
                    text(
                        """
                        UPDATE user_dashboard_preference
                        SET
                            module_order = CAST(:module_order AS jsonb),
                            hidden_modules = '["map", "removed_module"]'::jsonb
                        WHERE user_id = :user_id
                        """
                    ),
                    {"module_order": json.dumps(legacy_order), "user_id": user_id},
                )
                migrated_legacy = await get_dashboard_preference(connection, user_id=user_id)
                assert migrated_legacy.module_order == [*legacy_order, "activity"]
                assert migrated_legacy.hidden_modules == ["map", "activity"]
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
