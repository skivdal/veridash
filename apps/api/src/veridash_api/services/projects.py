"""Authorized project use cases."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncConnection

from veridash_api.db.sqlc import models as database_models
from veridash_api.db.sqlc.projects import AsyncQuerier
from veridash_api.errors import ApiProblem


async def create_project(
    connection: AsyncConnection,
    *,
    user_id: int,
    title: str,
) -> database_models.Project:
    project = await AsyncQuerier(connection).create_project(
        id=uuid4(),
        user_id=user_id,
        title=title,
    )
    if project is None:
        raise RuntimeError("INSERT ... RETURNING unexpectedly returned no project")
    return project


async def list_projects(
    connection: AsyncConnection,
    *,
    user_id: int,
) -> list[database_models.Project]:
    return [project async for project in AsyncQuerier(connection).list_projects(user_id=user_id)]


async def get_project(
    connection: AsyncConnection,
    *,
    user_id: int,
    project_id: UUID,
) -> database_models.Project:
    project = await AsyncQuerier(connection).get_project(id=project_id, user_id=user_id)
    if project is None:
        raise ApiProblem(
            status=404,
            code="project_not_found",
            title="Project not found",
            detail="The requested project does not exist.",
        )
    return project
