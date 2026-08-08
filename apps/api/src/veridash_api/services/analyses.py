"""Authorized analysis snapshots assembled from application-owned queries."""

from collections import defaultdict
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncConnection
from veridash_analysis import (
    AnalysisRegistry,
    ModuleManifest,
    analysis_cache_key,
    analysis_request_key,
    manifest_document,
    manifest_hash,
)
from veridash_analysis.stitching import StitchFramesParameters

from veridash_api.db.sqlc import models as database_models
from veridash_api.db.sqlc.analyses import (
    AsyncQuerier,
    CreateRequestedAnalysisJobParams,
    RegisterAnalysisDefinitionParams,
)
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


async def create_frame_stitch(
    connection: AsyncConnection,
    registry: AnalysisRegistry,
    *,
    user_id: int,
    project_id: UUID,
    selected_output_names: list[str],
) -> AnalysisJobResponse:
    """Create one idempotent user-requested stitch over the current keyframe result."""
    project = await get_project(connection, user_id=user_id, project_id=project_id)
    if project.state != database_models.ProjectState.ACTIVE:
        raise ApiProblem(
            status=409,
            code="project_archived",
            title="Project is archived",
            detail="Restore the project before starting a frame stitch.",
        )
    manifest = registry.get("stitch_frames")
    if manifest.automatic:
        raise RuntimeError("frame stitching must remain an explicit analysis")
    parameters = StitchFramesParameters(selected_output_names=selected_output_names)
    queries = AsyncQuerier(connection)
    frame_rows = [
        row
        async for row in queries.list_current_keyframe_artifacts(
            project_id=project_id,
            user_id=user_id,
        )
    ]
    if not frame_rows:
        raise ApiProblem(
            status=409,
            code="keyframes_not_ready",
            title="Frames are not ready",
            detail="Wait for frame extraction to finish before stitching frames.",
        )
    frames_by_name = {row.output_name: row for row in frame_rows}
    try:
        selected = [frames_by_name[name] for name in parameters.selected_output_names]
    except KeyError as exception:
        raise ApiProblem(
            status=422,
            code="invalid_frame_selection",
            title="Invalid frame selection",
            detail="Select frames from the current extracted-frame result.",
        ) from exception
    first = selected[0]
    if first.source_sha256 is None:
        raise RuntimeError("current keyframes reference source media without a content hash")
    if any(
        row.job_id != first.job_id
        or row.source_media_id != first.source_media_id
        or row.request_key != first.request_key
        or row.source_sha256 != first.source_sha256
        or row.kind != database_models.AnalysisArtifactKind.BLOB
        or row.media_type != "image/jpeg"
        or row.schema_id != "veridash.keyframe.jpeg"
        or row.schema_version != 1
        for row in selected
    ):
        raise RuntimeError("current keyframe artifacts violate the installed input contract")
    request_key = analysis_request_key(
        manifest,
        source_sha256=first.source_sha256,
        parameters=parameters,
        dependency_request_keys={"extract_keyframes": first.request_key},
    )
    cache_key = analysis_cache_key(
        manifest,
        source_sha256=first.source_sha256,
        parameters=parameters,
        dependency_artifact_hashes={
            "extract_keyframes": {row.output_name: row.sha256_hex for row in selected}
        },
    )
    definition = await queries.register_analysis_definition(
        RegisterAnalysisDefinitionParams(
            module_id=manifest.module_id,
            implementation_version=manifest.version,
            display_name=manifest.display_name,
            result_schema_version=manifest.result_schema_version,
            resource_class=database_models.AnalysisResourceClass(manifest.resource_class.value),
            automatic=manifest.automatic,
            manifest_hash=manifest_hash(manifest),
            manifest=manifest_document(manifest),
        )
    )
    if definition is None:
        raise RuntimeError("frame-stitch definition registration returned no row")
    if definition.manifest_hash != manifest_hash(manifest):
        raise RuntimeError("frame-stitch definition version was reused with another manifest")
    job = await queries.create_requested_analysis_job(
        CreateRequestedAnalysisJobParams(
            id=uuid4(),
            project_id=project_id,
            source_media_id=first.source_media_id,
            module_id=manifest.module_id,
            implementation_version=manifest.version,
            parameters=parameters.model_dump_json(),
            request_key=request_key,
            cache_key=cache_key,
            priority=manifest.priority,
            max_attempts=manifest.max_attempts,
        )
    )
    if job is None:
        raise RuntimeError("frame-stitch job creation returned no row")
    await queries.add_analysis_job_dependency(
        project_id=project_id,
        job_id=job.id,
        depends_on_job_id=first.job_id,
    )
    for response in await list_project_analyses(
        connection,
        user_id=user_id,
        project_id=project_id,
    ):
        if response.id == job.id:
            return response
    raise RuntimeError("created frame-stitch job disappeared from the project snapshot")


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
