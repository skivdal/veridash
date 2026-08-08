"""Analysis snapshot routes; scheduling is never triggered by reads."""

from uuid import UUID

from fastapi import APIRouter

from veridash_api.auth.dependencies import CurrentSession
from veridash_api.database import DatabaseConnection
from veridash_api.models import PROBLEM_RESPONSE, AnalysisJobResponse
from veridash_api.services import analyses as analysis_service

router = APIRouter(tags=["analyses"])


@router.get(
    "/projects/{project_id}/analyses",
    response_model=list[AnalysisJobResponse],
    responses={
        401: {**PROBLEM_RESPONSE, "description": "Authentication required"},
        404: {**PROBLEM_RESPONSE, "description": "Project not found"},
    },
)
async def list_project_analyses(
    project_id: UUID,
    connection: DatabaseConnection,
    session: CurrentSession,
) -> list[AnalysisJobResponse]:
    return await analysis_service.list_project_analyses(
        connection,
        user_id=session.user_id,
        project_id=project_id,
    )
