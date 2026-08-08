"""Authorized analysis snapshots assembled from application-owned queries."""

from collections import defaultdict
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncConnection
from veridash_analysis import ModuleManifest

from veridash_api.db.sqlc.analyses import AsyncQuerier
from veridash_api.errors import ApiProblem
from veridash_api.models import (
    AnalysisArtifactResponse,
    AnalysisAttemptResponse,
    AnalysisJobResponse,
)
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
        manifest = ModuleManifest.model_validate(job.manifest)
        if (
            manifest.module_id != job.module_id
            or manifest.version != job.implementation_version
            or manifest.result_schema_version != job.result_schema_version
        ):
            raise RuntimeError("analysis definition columns disagree with its manifest")
        responses.append(
            AnalysisJobResponse(
                id=job.id,
                project_id=job.project_id,
                source_media_id=job.source_media_id,
                module_id=job.module_id,
                implementation_version=job.implementation_version,
                result_schema_version=job.result_schema_version,
                display_name=job.display_name,
                resource_class=job.resource_class,
                cacheable=manifest.cacheable,
                implementation_fingerprints={
                    item.name: item.value for item in manifest.fingerprints
                },
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


async def retry_project_analysis(
    connection: AsyncConnection,
    *,
    user_id: int,
    project_id: UUID,
    job_id: UUID,
) -> AnalysisJobResponse:
    """Retry a terminal job and restore dependency-blocked descendants."""
    await get_project(connection, user_id=user_id, project_id=project_id)
    queries = AsyncQuerier(connection)
    retried = await queries.request_project_analysis_job_retry(
        job_id=job_id,
        project_id=project_id,
        user_id=user_id,
    )
    if retried is None:
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
            code="analysis_job_not_retryable",
            title="Analysis cannot be retried",
            detail="This analysis is already active, complete, or has reached its retry limit.",
        )

    analyses = await list_project_analyses(
        connection,
        user_id=user_id,
        project_id=project_id,
    )
    for analysis in analyses:
        if analysis.id == job_id:
            return analysis
    raise RuntimeError("retried analysis disappeared from its project snapshot")


async def list_project_analysis_artifacts(
    connection: AsyncConnection,
    *,
    user_id: int,
    project_id: UUID,
    job_id: UUID,
) -> list[AnalysisArtifactResponse]:
    await get_project(connection, user_id=user_id, project_id=project_id)
    queries = AsyncQuerier(connection)
    job = await queries.get_analysis_job(job_id=job_id, user_id=user_id)
    if job is None or job.project_id != project_id:
        raise ApiProblem(
            status=404,
            code="analysis_job_not_found",
            title="Analysis not found",
            detail="The requested analysis does not exist.",
        )
    return [
        AnalysisArtifactResponse.model_validate(artifact, from_attributes=True)
        async for artifact in queries.list_analysis_job_artifacts(
            job_id=job_id,
            user_id=user_id,
        )
    ]


async def get_project_analysis_blob_artifact(
    connection: AsyncConnection,
    *,
    user_id: int,
    project_id: UUID,
    job_id: UUID,
    artifact_id: UUID,
):
    artifact = await AsyncQuerier(connection).get_project_analysis_blob_artifact(
        project_id=project_id,
        job_id=job_id,
        artifact_id=artifact_id,
        user_id=user_id,
    )
    if artifact is None:
        raise ApiProblem(
            status=404,
            code="analysis_artifact_not_found",
            title="Analysis artifact not found",
            detail="The requested analysis artifact does not exist.",
        )
    if artifact.blob_key is None or artifact.blob_key != artifact.sha256_hex:
        raise RuntimeError("blob artifact has no valid immutable storage identity")
    return artifact
