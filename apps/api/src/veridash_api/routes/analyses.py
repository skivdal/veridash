"""Analysis snapshot routes; scheduling is never triggered by reads."""

from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse

from veridash_api.auth.dependencies import ApiSettings, CurrentSession, MutationSession
from veridash_api.database import DatabaseConnection, DatabaseEngine
from veridash_api.errors import ApiProblem
from veridash_api.models import PROBLEM_RESPONSE, AnalysisArtifactResponse, AnalysisJobResponse
from veridash_api.services import analyses as analysis_service
from veridash_api.services import events as event_service
from veridash_api.services.auth import authentication_required_problem, resolve_session
from veridash_api.services.projects import get_project

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


@router.post(
    "/projects/{project_id}/analyses/{job_id}/cancel",
    response_model=AnalysisJobResponse,
    responses={
        401: {**PROBLEM_RESPONSE, "description": "Authentication required"},
        403: {**PROBLEM_RESPONSE, "description": "CSRF check failed"},
        404: {**PROBLEM_RESPONSE, "description": "Analysis not found"},
        409: {**PROBLEM_RESPONSE, "description": "Analysis already finished"},
    },
)
async def cancel_project_analysis(
    project_id: UUID,
    job_id: UUID,
    connection: DatabaseConnection,
    session: MutationSession,
) -> AnalysisJobResponse:
    return await analysis_service.cancel_project_analysis(
        connection,
        user_id=session.user_id,
        project_id=project_id,
        job_id=job_id,
    )


@router.get(
    "/projects/{project_id}/analyses/{job_id}/artifacts",
    response_model=list[AnalysisArtifactResponse],
    responses={
        401: {**PROBLEM_RESPONSE, "description": "Authentication required"},
        404: {**PROBLEM_RESPONSE, "description": "Analysis not found"},
    },
)
async def list_project_analysis_artifacts(
    project_id: UUID,
    job_id: UUID,
    connection: DatabaseConnection,
    session: CurrentSession,
) -> list[AnalysisArtifactResponse]:
    return await analysis_service.list_project_analysis_artifacts(
        connection,
        user_id=session.user_id,
        project_id=project_id,
        job_id=job_id,
    )


@router.get(
    "/projects/{project_id}/events",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Durable project event stream",
            "content": {"text/event-stream": {}},
        },
        400: {**PROBLEM_RESPONSE, "description": "Invalid replay cursor"},
        401: {**PROBLEM_RESPONSE, "description": "Authentication required"},
        404: {**PROBLEM_RESPONSE, "description": "Project not found"},
    },
)
async def stream_project_events(
    project_id: UUID,
    request: Request,
    engine: DatabaseEngine,
    settings: ApiSettings,
    after: int | None = Query(default=None, ge=0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token is None:
        raise authentication_required_problem()
    replay_cursor = _parse_event_cursor(last_event_id) if last_event_id is not None else after
    async with engine.begin() as connection:
        session = await resolve_session(connection, raw_token=raw_token)
        await get_project(connection, user_id=session.user_id, project_id=project_id)

    return StreamingResponse(
        event_service.stream_project_events(
            engine,
            user_id=session.user_id,
            project_id=project_id,
            after_event_id=replay_cursor or 0,
            send_initial_sync=replay_cursor is None,
            poll_interval_seconds=settings.event_poll_interval_seconds,
            keepalive_seconds=settings.event_keepalive_seconds,
            lifetime_seconds=settings.event_stream_lifetime_seconds,
            batch_size=settings.event_batch_size,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _parse_event_cursor(value: str) -> int:
    try:
        cursor = int(value)
    except ValueError:
        cursor = -1
    if cursor < 0:
        raise ApiProblem(
            status=400,
            code="invalid_event_cursor",
            title="Invalid event cursor",
            detail="Reconnect without the saved event cursor.",
        )
    return cursor
