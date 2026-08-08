"""Database-backed authentication use cases."""

import datetime
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from veridash_api.auth.passwords import PASSWORD_HASH, verify_password
from veridash_api.auth.tokens import hash_session_token, new_session_token
from veridash_api.db.sqlc.auth import AsyncQuerier
from veridash_api.errors import ApiProblem

# Verifying a real hash for unknown usernames keeps the dominant login work similar.
_DUMMY_PASSWORD_HASH = PASSWORD_HASH.hash("not-a-real-user-password")


@dataclass(frozen=True)
class AuthenticatedSession:
    user_id: int
    username: str
    session_id: UUID
    expires_at: datetime.datetime
    raw_token: str = field(repr=False)


def normalize_username(username: str) -> str:
    return username.strip().lower()


def invalid_credentials_problem() -> ApiProblem:
    return ApiProblem(
        status=401,
        code="invalid_credentials",
        title="Authentication failed",
        detail="The username or password is incorrect.",
    )


def authentication_required_problem() -> ApiProblem:
    return ApiProblem(
        status=401,
        code="authentication_required",
        title="Authentication required",
        detail="Sign in to continue.",
    )


def login_throttled_problem() -> ApiProblem:
    return ApiProblem(
        status=429,
        code="login_throttled",
        title="Too many sign-in attempts",
        detail="Wait 15 minutes before trying to sign in again.",
        headers={"Retry-After": "900"},
    )


async def log_in(
    engine: AsyncEngine,
    *,
    username: str,
    password: str,
    session_ttl_seconds: int,
    remote_address: str,
) -> AuthenticatedSession:
    """Verify credentials and persist a revocable opaque session."""
    async with engine.connect() as connection:
        queries = AsyncQuerier(connection)
        if await queries.is_login_blocked(remote_address=remote_address):
            raise login_throttled_problem()
        user = await queries.get_user_by_username(username=normalize_username(username))

    credentials_are_valid = False
    if user is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
    elif user.is_enabled:
        credentials_are_valid = verify_password(password, user.password_hash)

    if user is None or not credentials_are_valid:
        async with engine.begin() as connection:
            await AsyncQuerier(connection).record_login_failure(remote_address=remote_address)
        raise invalid_credentials_problem()

    token = new_session_token()
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        seconds=session_ttl_seconds
    )
    async with engine.begin() as connection:
        queries = AsyncQuerier(connection)
        session = await queries.create_session(
            id=uuid4(),
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=expires_at,
        )
        await queries.clear_login_failures(remote_address=remote_address)
    if session is None:
        raise RuntimeError("INSERT ... RETURNING unexpectedly returned no session")

    return AuthenticatedSession(
        user_id=user.id,
        username=user.username,
        session_id=session.id,
        expires_at=session.expires_at,
        raw_token=token,
    )


async def resolve_session(
    connection: AsyncConnection,
    *,
    raw_token: str,
) -> AuthenticatedSession:
    """Resolve only active sessions belonging to an enabled account."""
    queries = AsyncQuerier(connection)
    token_hash = hash_session_token(raw_token)
    session = await queries.get_active_session_user(token_hash=token_hash)
    if session is None:
        raise authentication_required_problem()

    await queries.touch_session(token_hash=token_hash)
    return AuthenticatedSession(
        user_id=session.user_id,
        username=session.username,
        session_id=session.session_id,
        expires_at=session.expires_at,
        raw_token=raw_token,
    )


async def log_out(connection: AsyncConnection, *, raw_token: str) -> None:
    await AsyncQuerier(connection).revoke_session(token_hash=hash_session_token(raw_token))
