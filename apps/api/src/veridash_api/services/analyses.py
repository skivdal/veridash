"""Authorized analysis snapshots assembled from application-owned queries."""

from collections import defaultdict
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncConnection

from veridash_api.db.sqlc.analyses import AsyncQuerier
from veridash_api.errors import ApiProblem
from veridash_api.models import AnalysisAttemptResponse, AnalysisJobResponse
from veridash_api.services.projects import get_project

PARAMETER_DOCUMENT = TypeAdapter(dict[str, object])


async def list_project_analyses(
    connection: AsyncConnection,
    *,
    user_id: int,
    project_id: UUID,
) -> list[AnalysisJobResponse]:
    await get_project(connection, user_id=user_id, project_id=project_id)
    queries = AsyncQuerier(connection)
    attempts_by_job: dict[UUID, list[AnalysisAttemptResponse]] = defaultdict(list)
    async for attempt in queries.list_project_analysis_attempts(
        project_id=project_id,
        user_id=user_id,
    ):
        attempts_by_job[attempt.job_id].append(
            AnalysisAttemptResponse.model_validate(attempt, from_attributes=True)
        )

    responses: list[AnalysisJobResponse] = []
    async for job in queries.list_project_analysis_jobs(
        project_id=project_id,
        user_id=user_id,
    ):
        parameter_document = PARAMETER_DOCUMENT.validate_python(job.parameters)
        responses.append(
            AnalysisJobResponse(
                id=job.id,
                project_id=job.project_id,
                source_media_id=job.source_media_id,
                module_id=job.module_id,
                implementation_version=job.implementation_version,
                display_name=job.display_name,
                resource_class=job.resource_class,
                state=job.state,
                parameters=parameter_document,
                max_attempts=job.max_attempts,
                next_attempt_at=job.next_attempt_at,
                ready_at=job.ready_at,
                started_at=job.started_at,
                finished_at=job.finished_at,
                cancel_requested_at=job.cancel_requested_at,
                failure_kind=job.failure_kind,
                public_failure_message=job.public_failure_message,
                diagnostic_id=job.diagnostic_id,
                reused=job.reused_from_job_id is not None,
                created_at=job.created_at,
                updated_at=job.updated_at,
                attempts=attempts_by_job[job.id],
            )
        )
    return responses


async def cancel_project_analysis(
    connection: AsyncConnection,
    *,
    user_id: int,
    project_id: UUID,
    job_id: UUID,
) -> AnalysisJobResponse:
    """Request cancellation, making non-running jobs terminal immediately."""
    await get_project(connection, user_id=user_id, project_id=project_id)
    queries = AsyncQuerier(connection)
    canceled = await queries.request_project_analysis_job_cancellation(
        job_id=job_id,
        project_id=project_id,
        user_id=user_id,
    )
    if canceled is None:
        existing = await queries.get_analysis_job(job_id=job_id, user_id=user_id)
        if existing is None or existing.project_id != project_id:
            raise ApiProblem(
                status=404,
                code="analysis_job_not_found",
                title="Analysis not found",
                detail="The requested analysis does not exist.",
            )
        raise ApiProblem(
            status=409,
            code="analysis_job_not_cancelable",
            title="Analysis cannot be canceled",
            detail="This analysis has already finished.",
        )

    analyses = await list_project_analyses(
        connection,
        user_id=user_id,
        project_id=project_id,
    )
    for analysis in analyses:
        if analysis.id == job_id:
            return analysis
    raise RuntimeError("canceled analysis disappeared from its project snapshot")
