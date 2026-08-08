"""Source-video reservation, streaming upload, completion, and playback."""

from collections.abc import Iterator
from typing import Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Request, status
from fastapi.responses import StreamingResponse
from veridash_storage import BlobTooLargeError

from veridash_api.analysis import ApiAnalysisRegistry
from veridash_api.auth.dependencies import ApiSettings, CurrentSession, MutationSession
from veridash_api.database import DatabaseConnection, DatabaseEngine
from veridash_api.db.sqlc import models as database_models
from veridash_api.errors import ApiProblem
from veridash_api.media_ranges import InvalidRangeError, parse_byte_range
from veridash_api.models import (
    PROBLEM_RESPONSE,
    ReserveSourceMediaRequest,
    SourceMediaResponse,
)
from veridash_api.services import media as media_service
from veridash_api.storage import ApiBlobStore

router = APIRouter(tags=["source media"])
MEDIA_MUTATION_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {**PROBLEM_RESPONSE, "description": "Authentication required"},
    403: {**PROBLEM_RESPONSE, "description": "CSRF check failed"},
    404: {**PROBLEM_RESPONSE, "description": "Project or source video not found"},
    409: {**PROBLEM_RESPONSE, "description": "Media state conflict"},
    413: {**PROBLEM_RESPONSE, "description": "Upload too large"},
    422: {**PROBLEM_RESPONSE, "description": "Invalid request or media"},
}


def _response(media: object) -> SourceMediaResponse:
    return SourceMediaResponse.model_validate(media)


@router.post(
    "/projects/{project_id}/media",
    response_model=SourceMediaResponse,
    responses=MEDIA_MUTATION_RESPONSES,
)
async def reserve_source_media(
    project_id: UUID,
    payload: ReserveSourceMediaRequest,
    connection: DatabaseConnection,
    session: MutationSession,
) -> SourceMediaResponse:
    media = await media_service.reserve_source_media(
        connection,
        user_id=session.user_id,
        project_id=project_id,
        original_filename=payload.original_filename,
    )
    return _response(media)


@router.get(
    "/projects/{project_id}/media",
    response_model=SourceMediaResponse,
    responses={
        401: {**PROBLEM_RESPONSE, "description": "Authentication required"},
        404: {**PROBLEM_RESPONSE, "description": "Project or source video not found"},
    },
)
async def get_project_source_media(
    project_id: UUID,
    connection: DatabaseConnection,
    session: CurrentSession,
) -> SourceMediaResponse:
    media = await media_service.get_project_source_media(
        connection,
        user_id=session.user_id,
        project_id=project_id,
    )
    return _response(media)


@router.put(
    "/uploads/{media_id}/content",
    response_model=SourceMediaResponse,
    responses=MEDIA_MUTATION_RESPONSES,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def upload_source_media_content(
    media_id: UUID,
    request: Request,
    connection: DatabaseConnection,
    session: MutationSession,
    settings: ApiSettings,
    store: ApiBlobStore,
) -> SourceMediaResponse:
    await media_service.require_uploadable_media(
        connection,
        user_id=session.user_id,
        media_id=media_id,
    )
    content_length = request.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared_size = int(content_length)
        except ValueError:
            raise ApiProblem(
                status=400,
                code="invalid_content_length",
                title="Invalid upload length",
                detail="The Content-Length header must be a non-negative integer.",
            ) from None
        if declared_size < 0:
            raise ApiProblem(
                status=400,
                code="invalid_content_length",
                title="Invalid upload length",
                detail="The Content-Length header must be a non-negative integer.",
            )
        if declared_size > settings.max_upload_bytes:
            raise _upload_too_large_problem(settings.max_upload_bytes)

    try:
        staged = await store.stage(
            str(media_id),
            request.stream(),
            max_bytes=settings.max_upload_bytes,
        )
    except BlobTooLargeError:
        raise _upload_too_large_problem(settings.max_upload_bytes) from None

    supplied_media_type = request.headers.get("Content-Type", "application/octet-stream")
    media_type = supplied_media_type.partition(";")[0].strip().lower()
    if not media_type or len(media_type) > 255:
        media_type = "application/octet-stream"
    media = await media_service.record_upload_content(
        connection,
        user_id=session.user_id,
        media_id=media_id,
        media_type=media_type,
        size_bytes=staged.size_bytes,
        sha256_hex=staged.sha256,
    )
    return _response(media)


def _upload_too_large_problem(max_upload_bytes: int) -> ApiProblem:
    return ApiProblem(
        status=413,
        code="upload_too_large",
        title="Video is too large",
        detail=f"The source video must not exceed {max_upload_bytes} bytes.",
    )


@router.post(
    "/uploads/{media_id}/complete",
    response_model=SourceMediaResponse,
    responses={
        **MEDIA_MUTATION_RESPONSES,
        503: {**PROBLEM_RESPONSE, "description": "Media validation unavailable"},
    },
)
async def complete_source_media_upload(
    media_id: UUID,
    engine: DatabaseEngine,
    session: MutationSession,
    settings: ApiSettings,
    store: ApiBlobStore,
    registry: ApiAnalysisRegistry,
) -> SourceMediaResponse:
    media = await media_service.complete_upload(
        engine,
        store,
        settings,
        registry,
        user_id=session.user_id,
        media_id=media_id,
    )
    return _response(media)


@router.get(
    "/media/{media_id}/content",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Complete source video",
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        },
        206: {"description": "Source video byte range"},
        401: {**PROBLEM_RESPONSE, "description": "Authentication required"},
        404: {**PROBLEM_RESPONSE, "description": "Source video not found"},
        409: {**PROBLEM_RESPONSE, "description": "Source video is not uploaded"},
        416: {**PROBLEM_RESPONSE, "description": "Range not satisfiable"},
    },
)
async def stream_source_media(
    media_id: UUID,
    request: Request,
    connection: DatabaseConnection,
    session: CurrentSession,
    store: ApiBlobStore,
) -> StreamingResponse:
    media = await media_service.get_source_media(
        connection,
        user_id=session.user_id,
        media_id=media_id,
    )
    if (
        media.upload_state != database_models.MediaUploadState.UPLOADED
        or media.sha256_hex is None
        or media.size_bytes is None
        or media.media_type is None
    ):
        raise ApiProblem(
            status=409,
            code="source_media_not_ready",
            title="Source video is not ready",
            detail="Finish uploading the source video before playing it.",
        )
    if not store.exists(media.sha256_hex):
        raise RuntimeError("uploaded source-media row references a missing blob")

    try:
        requested_range = parse_byte_range(
            request.headers.get("Range"),
            size_bytes=media.size_bytes,
        )
    except InvalidRangeError:
        raise ApiProblem(
            status=416,
            code="range_not_satisfiable",
            title="Requested range is not available",
            detail="Request a single byte range within the source video.",
            headers={"Content-Range": f"bytes */{media.size_bytes}"},
        ) from None

    start = requested_range.start if requested_range is not None else 0
    end = requested_range.end if requested_range is not None else media.size_bytes - 1
    length = end - start + 1
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Content-Disposition": (
            "inline; filename*=UTF-8''" + quote(media.original_filename, safe="")
        ),
    }
    response_status = status.HTTP_200_OK
    if requested_range is not None:
        response_status = status.HTTP_206_PARTIAL_CONTENT
        headers["Content-Range"] = f"bytes {start}-{end}/{media.size_bytes}"

    return StreamingResponse(
        _read_blob_range(store, media.sha256_hex, start=start, length=length),
        status_code=response_status,
        media_type=media.media_type,
        headers=headers,
    )


def _read_blob_range(
    store: ApiBlobStore,
    sha256: str,
    *,
    start: int,
    length: int,
) -> Iterator[bytes]:
    remaining = length
    with store.open(sha256) as source:
        source.seek(start)
        while remaining > 0:
            chunk = source.read(min(1024 * 1024, remaining))
            if not chunk:
                raise RuntimeError("blob ended before its recorded size")
            remaining -= len(chunk)
            yield chunk
