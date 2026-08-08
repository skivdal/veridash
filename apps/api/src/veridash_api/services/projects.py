"""Authorized project use cases."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncConnection

from veridash_api.db.sqlc import models as database_models
from veridash_api.db.sqlc.projects import AsyncQuerier, GetProjectNoteRow, SaveProjectNoteRow
from veridash_api.errors import ApiProblem


def project_not_found_problem() -> ApiProblem:
    return ApiProblem(
        status=404,
        code="project_not_found",
        title="Project not found",
        detail="The requested project does not exist.",
    )


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
        raise project_not_found_problem()
    return project


async def rename_project(
    connection: AsyncConnection,
    *,
    user_id: int,
    project_id: UUID,
    title: str,
) -> database_models.Project:
    project = await AsyncQuerier(connection).rename_project(
        id=project_id,
        user_id=user_id,
        title=title,
    )
    if project is None:
        raise project_not_found_problem()
    return project


async def archive_project(
    connection: AsyncConnection,
    *,
    user_id: int,
    project_id: UUID,
) -> database_models.Project:
    project = await AsyncQuerier(connection).archive_project(id=project_id, user_id=user_id)
    if project is None:
        raise project_not_found_problem()
    return project


async def restore_project(
    connection: AsyncConnection,
    *,
    user_id: int,
    project_id: UUID,
) -> database_models.Project:
    project = await AsyncQuerier(connection).restore_project(id=project_id, user_id=user_id)
    if project is None:
        raise project_not_found_problem()
    return project


async def get_project_note(
    connection: AsyncConnection,
    *,
    user_id: int,
    project_id: UUID,
) -> GetProjectNoteRow:
    note = await AsyncQuerier(connection).get_project_note(
        project_id=project_id,
        user_id=user_id,
    )
    if note is None:
        raise project_not_found_problem()
    return note


async def save_project_note(
    connection: AsyncConnection,
    *,
    user_id: int,
    project_id: UUID,
    body: str,
    expected_revision: int,
) -> SaveProjectNoteRow:
    note = await AsyncQuerier(connection).save_project_note(
        body=body,
        expected_revision=expected_revision,
        project_id=project_id,
        user_id=user_id,
    )
    if note is not None:
        return note
    await get_project(connection, user_id=user_id, project_id=project_id)
    raise ApiProblem(
        status=409,
        code="note_revision_conflict",
        title="Notes changed",
        detail="Reload the saved notes before editing further.",
    )
