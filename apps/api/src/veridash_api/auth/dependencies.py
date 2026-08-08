"""FastAPI dependencies for authenticated and CSRF-protected requests."""

from typing import Annotated, cast

from fastapi import Depends, Request

from veridash_api.auth.tokens import csrf_token_matches
from veridash_api.config import Settings
from veridash_api.database import DatabaseConnection
from veridash_api.errors import ApiProblem
from veridash_api.services.auth import AuthenticatedSession, resolve_session


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


ApiSettings = Annotated[Settings, Depends(get_settings)]


async def require_session(
    request: Request,
    connection: DatabaseConnection,
    settings: ApiSettings,
) -> AuthenticatedSession:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token is None:
        from veridash_api.services.auth import authentication_required_problem

        raise authentication_required_problem()
    return await resolve_session(connection, raw_token=raw_token)


CurrentSession = Annotated[AuthenticatedSession, Depends(require_session)]


async def require_csrf_session(
    request: Request,
    session: CurrentSession,
    settings: ApiSettings,
) -> AuthenticatedSession:
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get("X-CSRF-Token")
    if (
        cookie_token is None
        or header_token is None
        or not csrf_token_matches(session.raw_token, cookie_token, header_token)
    ):
        raise ApiProblem(
            status=403,
            code="csrf_check_failed",
            title="Request rejected",
            detail="Refresh the page and try again.",
        )
    return session


MutationSession = Annotated[AuthenticatedSession, Depends(require_csrf_session)]
