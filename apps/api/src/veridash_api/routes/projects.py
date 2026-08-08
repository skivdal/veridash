"""Thin project HTTP adapter."""

from uuid import UUID

from fastapi import APIRouter, status

from veridash_api.auth.dependencies import CurrentSession, MutationSession
from veridash_api.database import DatabaseConnection
from veridash_api.models import PROBLEM_RESPONSE, CreateProjectRequest, ProjectResponse
from veridash_api.services import projects as project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {**PROBLEM_RESPONSE, "description": "Authentication required"},
        403: {**PROBLEM_RESPONSE, "description": "CSRF check failed"},
        422: {**PROBLEM_RESPONSE, "description": "Invalid request"},
    },
)
async def create_project(
    payload: CreateProjectRequest,
    connection: DatabaseConnection,
    session: MutationSession,
) -> ProjectResponse:
    project = await project_service.create_project(
        connection,
        user_id=session.user_id,
        title=payload.title,
    )
    return ProjectResponse.model_validate(project)


@router.get(
    "",
    response_model=list[ProjectResponse],
    responses={401: {**PROBLEM_RESPONSE, "description": "Authentication required"}},
)
async def list_projects(
    connection: DatabaseConnection,
    session: CurrentSession,
) -> list[ProjectResponse]:
    projects = await project_service.list_projects(connection, user_id=session.user_id)
    return [ProjectResponse.model_validate(project) for project in projects]


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={
        401: {**PROBLEM_RESPONSE, "description": "Authentication required"},
        404: {**PROBLEM_RESPONSE, "description": "Project not found"},
        422: {**PROBLEM_RESPONSE, "description": "Invalid request"},
    },
)
async def get_project(
    project_id: UUID,
    connection: DatabaseConnection,
    session: CurrentSession,
) -> ProjectResponse:
    project = await project_service.get_project(
        connection,
        user_id=session.user_id,
        project_id=project_id,
    )
    return ProjectResponse.model_validate(project)
