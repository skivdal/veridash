"""Authorized source-media reservation, staging, validation, and publication."""

import asyncio
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from veridash_storage import UploadBlobStore

from veridash_api.config import Settings
from veridash_api.db.sqlc import models as database_models
from veridash_api.db.sqlc.media import (
    AsyncQuerier,
    MarkSourceMediaUploadedParams,
    RecordUploadContentParams,
)
from veridash_api.errors import ApiProblem
from veridash_api.media_validation import (
    InvalidMediaError,
    MediaValidationUnavailableError,
    validate_video,
)
from veridash_api.services.projects import get_project


def media_not_found_problem() -> ApiProblem:
    return ApiProblem(
        status=404,
        code="media_not_found",
        title="Source video not found",
        detail="The requested source video does not exist.",
    )


def project_archived_problem() -> ApiProblem:
    return ApiProblem(
        status=409,
        code="project_archived",
        title="Project is archived",
        detail="Restore the project before changing its source video.",
    )


async def _require_active_project(
    connection: AsyncConnection,
    *,
    user_id: int,
    project_id: UUID,
) -> None:
    project = await get_project(connection, user_id=user_id, project_id=project_id)
    if project.state == database_models.ProjectState.ARCHIVED:
        raise project_archived_problem()


async def reserve_source_media(
    connection: AsyncConnection,
    *,
    user_id: int,
    project_id: UUID,
    original_filename: str,
) -> database_models.SourceMedium:
    """Idempotently reserve the one source-media resource for a project."""
    queries = AsyncQuerier(connection)
    await _require_active_project(connection, user_id=user_id, project_id=project_id)
    media = await queries.create_source_media(
        id=uuid4(),
        project_id=project_id,
        user_id=user_id,
        original_filename=original_filename,
    )
    if media is not None:
        return media

    # A concurrent retry may have won the unique project constraint.
    existing = await queries.get_source_media_for_project(
        project_id=project_id,
        user_id=user_id,
    )
    if existing is None:
        raise RuntimeError("source-media reservation disappeared after a uniqueness race")
    return existing


async def get_project_source_media(
    connection: AsyncConnection,
    *,
    user_id: int,
    project_id: UUID,
) -> database_models.SourceMedium:
    await get_project(connection, user_id=user_id, project_id=project_id)
    media = await AsyncQuerier(connection).get_source_media_for_project(
        project_id=project_id,
        user_id=user_id,
    )
    if media is None:
        raise media_not_found_problem()
    return media


async def get_source_media(
    connection: AsyncConnection,
    *,
    user_id: int,
    media_id: UUID,
) -> database_models.SourceMedium:
    media = await AsyncQuerier(connection).get_source_media(id=media_id, user_id=user_id)
    if media is None:
        raise media_not_found_problem()
    return media


async def require_uploadable_media(
    connection: AsyncConnection,
    *,
    user_id: int,
    media_id: UUID,
) -> database_models.SourceMedium:
    media = await get_source_media(connection, user_id=user_id, media_id=media_id)
    await _require_active_project(
        connection,
        user_id=user_id,
        project_id=media.project_id,
    )
    if media.upload_state == database_models.MediaUploadState.UPLOADED:
        raise ApiProblem(
            status=409,
            code="source_media_finalized",
            title="Source video already uploaded",
            detail="A project can contain only one immutable source video.",
        )
    return media


async def record_upload_content(
    connection: AsyncConnection,
    *,
    user_id: int,
    media_id: UUID,
    media_type: str,
    size_bytes: int,
    sha256_hex: str,
) -> database_models.SourceMedium:
    media = await AsyncQuerier(connection).record_upload_content(
        RecordUploadContentParams(
            media_type=media_type,
            size_bytes=size_bytes,
            sha256_hex=sha256_hex,
            media_id=media_id,
            user_id=user_id,
        )
    )
    if media is None:
        await require_uploadable_media(connection, user_id=user_id, media_id=media_id)
        raise RuntimeError("uploadable media could not record staged content")
    return media


async def complete_upload(
    engine: AsyncEngine,
    store: UploadBlobStore,
    settings: Settings,
    *,
    user_id: int,
    media_id: UUID,
) -> database_models.SourceMedium:
    async with engine.connect() as connection:
        media = await get_source_media(connection, user_id=user_id, media_id=media_id)
        await _require_active_project(
            connection,
            user_id=user_id,
            project_id=media.project_id,
        )

    if media.upload_state == database_models.MediaUploadState.UPLOADED:
        if media.sha256_hex is None or not store.exists(media.sha256_hex):
            raise RuntimeError("uploaded source-media row references a missing blob")
        return media
    if media.sha256_hex is None or media.size_bytes is None:
        raise ApiProblem(
            status=409,
            code="upload_incomplete",
            title="Upload incomplete",
            detail="Upload the complete video content before finalizing it.",
        )

    staging_path = store.staging_path(str(media.id))
    if not staging_path.is_file():
        raise ApiProblem(
            status=409,
            code="upload_content_missing",
            title="Upload content missing",
            detail="Upload the video content again before finalizing it.",
        )

    try:
        validated = await validate_video(
            staging_path,
            ffprobe_executable=settings.ffprobe_executable,
            timeout_seconds=settings.media_validation_timeout_seconds,
        )
    except InvalidMediaError as exception:
        async with engine.begin() as connection:
            await AsyncQuerier(connection).mark_source_media_failed(
                failure_message=str(exception),
                media_id=media_id,
                user_id=user_id,
            )
        raise ApiProblem(
            status=422,
            code="invalid_media",
            title="Invalid source video",
            detail=str(exception),
        ) from None
    except MediaValidationUnavailableError:
        raise ApiProblem(
            status=503,
            code="media_validation_unavailable",
            title="Video validation unavailable",
            detail="The video could not be validated right now. Try again later.",
        ) from None

    blob = await asyncio.to_thread(store.publish, staging_path, media_type=validated.media_type)
    if blob.sha256 != media.sha256_hex or blob.size_bytes != media.size_bytes:
        raise ApiProblem(
            status=409,
            code="upload_changed",
            title="Upload changed during validation",
            detail="Upload the video content again before finalizing it.",
        )

    async with engine.begin() as connection:
        completed = await AsyncQuerier(connection).mark_source_media_uploaded(
            MarkSourceMediaUploadedParams(
                media_type=blob.media_type,
                size_bytes=blob.size_bytes,
                sha256_hex=blob.sha256,
                blob_key=blob.sha256,
                media_id=media_id,
                user_id=user_id,
            )
        )
    if completed is None:
        raise ApiProblem(
            status=409,
            code="upload_changed",
            title="Upload changed during validation",
            detail="Refresh the project and try again.",
        )
    store.discard_staging(str(media_id))
    return completed
