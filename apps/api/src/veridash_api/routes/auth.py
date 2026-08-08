"""Thin authentication HTTP adapter."""

from fastapi import APIRouter, Request, Response, status

from veridash_api.auth.dependencies import ApiSettings, CurrentSession, MutationSession
from veridash_api.auth.tokens import derive_csrf_token
from veridash_api.database import DatabaseConnection, DatabaseEngine
from veridash_api.models import PROBLEM_RESPONSE, LoginRequest, SessionResponse, UserResponse
from veridash_api.services.auth import log_in, log_out

router = APIRouter(prefix="/auth", tags=["authentication"])


def _session_response(
    *, user_id: int, username: str, email: str, is_admin: bool
) -> SessionResponse:
    return SessionResponse(
        user=UserResponse(
            id=user_id,
            username=username,
            email=email,
            is_admin=is_admin,
        )
    )


def _set_session_cookies(
    response: Response,
    *,
    raw_token: str,
    settings: ApiSettings,
) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        raw_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        derive_csrf_token(raw_token),
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
    )


def _clear_session_cookies(response: Response, *, settings: ApiSettings) -> None:
    response.delete_cookie(
        settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(
        settings.csrf_cookie_name,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post(
    "/login",
    response_model=SessionResponse,
    responses={
        401: {**PROBLEM_RESPONSE, "description": "Invalid credentials"},
        429: {**PROBLEM_RESPONSE, "description": "Too many sign-in attempts"},
        422: {**PROBLEM_RESPONSE, "description": "Invalid request"},
    },
)
async def login(
    payload: LoginRequest,
    response: Response,
    engine: DatabaseEngine,
    settings: ApiSettings,
    request: Request,
) -> SessionResponse:
    remote_address = request.client.host if request.client is not None else "unknown"
    session = await log_in(
        engine,
        username=payload.username,
        password=payload.password,
        session_ttl_seconds=settings.session_ttl_seconds,
        remote_address=remote_address,
    )
    _set_session_cookies(response, raw_token=session.raw_token, settings=settings)
    return _session_response(
        user_id=session.user_id,
        username=session.username,
        email=session.email,
        is_admin=session.is_admin,
    )


@router.get(
    "/me",
    response_model=SessionResponse,
    responses={401: {**PROBLEM_RESPONSE, "description": "Authentication required"}},
)
async def get_current_user(session: CurrentSession) -> SessionResponse:
    return _session_response(
        user_id=session.user_id,
        username=session.username,
        email=session.email,
        is_admin=session.is_admin,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {**PROBLEM_RESPONSE, "description": "Authentication required"},
        403: {**PROBLEM_RESPONSE, "description": "CSRF check failed"},
    },
)
async def logout(
    response: Response,
    connection: DatabaseConnection,
    settings: ApiSettings,
    session: MutationSession,
) -> None:
    await log_out(connection, raw_token=session.raw_token)
    _clear_session_cookies(response, settings=settings)
