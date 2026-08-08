"""Authenticated dashboard presentation-preference routes."""

from fastapi import APIRouter

from veridash_api.auth.dependencies import CurrentSession, MutationSession
from veridash_api.database import DatabaseConnection
from veridash_api.models import (
    PROBLEM_RESPONSE,
    DashboardPreferenceResponse,
    SaveDashboardPreferenceRequest,
)
from veridash_api.services import preferences as preference_service

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get(
    "/dashboard",
    response_model=DashboardPreferenceResponse,
    responses={401: {**PROBLEM_RESPONSE, "description": "Authentication required"}},
)
async def get_dashboard_preference(
    connection: DatabaseConnection,
    session: CurrentSession,
) -> DashboardPreferenceResponse:
    return await preference_service.get_dashboard_preference(
        connection,
        user_id=session.user_id,
    )


@router.put(
    "/dashboard",
    response_model=DashboardPreferenceResponse,
    responses={
        401: {**PROBLEM_RESPONSE, "description": "Authentication required"},
        403: {**PROBLEM_RESPONSE, "description": "CSRF check failed"},
        409: {**PROBLEM_RESPONSE, "description": "Preference revision conflict"},
        422: {**PROBLEM_RESPONSE, "description": "Invalid dashboard settings"},
    },
)
async def save_dashboard_preference(
    payload: SaveDashboardPreferenceRequest,
    connection: DatabaseConnection,
    session: MutationSession,
) -> DashboardPreferenceResponse:
    return await preference_service.save_dashboard_preference(
        connection,
        user_id=session.user_id,
        module_order=payload.module_order,
        hidden_modules=payload.hidden_modules,
        expected_revision=payload.expected_revision,
    )
