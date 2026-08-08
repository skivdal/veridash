"""Durable user presentation preferences, separate from analysis state."""

import json

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncConnection

from veridash_api.db.sqlc.preferences import AsyncQuerier
from veridash_api.errors import ApiProblem
from veridash_api.models import DASHBOARD_MODULE_IDS, DashboardPreferenceResponse

STRING_LIST = TypeAdapter(list[str])


async def get_dashboard_preference(
    connection: AsyncConnection,
    *,
    user_id: int,
) -> DashboardPreferenceResponse:
    row = await AsyncQuerier(connection).get_dashboard_preference(user_id=user_id)
    if row is None:
        raise RuntimeError("authenticated user disappeared while loading preferences")
    order = STRING_LIST.validate_python(row.module_order)
    hidden = STRING_LIST.validate_python(row.hidden_modules)
    if row.revision == 0:
        order = [str(module_id) for module_id in DASHBOARD_MODULE_IDS]
    return DashboardPreferenceResponse(
        user_id=row.user_id,
        module_order=order,
        hidden_modules=hidden,
        revision=row.revision,
        updated_at=row.updated_at,
    )


async def save_dashboard_preference(
    connection: AsyncConnection,
    *,
    user_id: int,
    module_order: list[str],
    hidden_modules: list[str],
    expected_revision: int,
) -> DashboardPreferenceResponse:
    row = await AsyncQuerier(connection).save_dashboard_preference(
        user_id=user_id,
        module_order=json.dumps(module_order, separators=(",", ":")),
        hidden_modules=json.dumps(hidden_modules, separators=(",", ":")),
        expected_revision=expected_revision,
    )
    if row is None:
        raise ApiProblem(
            status=409,
            code="dashboard_preference_revision_conflict",
            title="Dashboard settings changed",
            detail="Reload the saved dashboard settings before editing further.",
        )
    return DashboardPreferenceResponse(
        user_id=row.user_id,
        module_order=STRING_LIST.validate_python(row.module_order),
        hidden_modules=STRING_LIST.validate_python(row.hidden_modules),
        revision=row.revision,
        updated_at=row.updated_at,
    )
