"""Administrator-owned local account management use cases."""

import re

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from veridash_api.auth.passwords import hash_password
from veridash_api.db.sqlc.admin import AsyncQuerier as AdminQuerier
from veridash_api.db.sqlc.auth import AsyncQuerier as AuthQuerier
from veridash_api.errors import ApiProblem
from veridash_api.models import AdminUserResponse
from veridash_api.services.auth import normalize_username


def _response(row: object) -> AdminUserResponse:
    return AdminUserResponse.model_validate(row, from_attributes=True)


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if len(normalized) > 320 or re.fullmatch(r"[^\s@]+@[^\s@]+", normalized) is None:
        raise ValueError("email address is invalid")
    return normalized


async def list_users(connection: AsyncConnection) -> list[AdminUserResponse]:
    return [_response(row) async for row in AdminQuerier(connection).list_admin_users()]


async def create_user(
    connection: AsyncConnection,
    *,
    username: str,
    email: str,
    password: str,
) -> AdminUserResponse:
    try:
        async with connection.begin_nested():
            created = await AuthQuerier(connection).create_user(
                username=normalize_username(username),
                email=normalize_email(email),
                password_hash=hash_password(password),
                is_admin=False,
            )
    except IntegrityError:
        raise ApiProblem(
            status=409,
            code="user_already_exists",
            title="User already exists",
            detail="That username or email address is already registered.",
        ) from None
    if created is None:
        raise RuntimeError("INSERT ... RETURNING unexpectedly returned no user")
    row = await AdminQuerier(connection).get_admin_user(user_id=created.id)
    if row is None:
        raise RuntimeError("newly created user could not be read")
    return _response(row)


async def deactivate_user(
    connection: AsyncConnection,
    *,
    user_id: int,
) -> AdminUserResponse:
    queries = AdminQuerier(connection)
    target = await queries.get_admin_user(user_id=user_id)
    if target is None:
        raise ApiProblem(
            status=404,
            code="user_not_found",
            title="User not found",
            detail="The requested user does not exist.",
        )
    if target.is_admin:
        raise ApiProblem(
            status=409,
            code="administrator_deactivation_forbidden",
            title="Administrator cannot be deactivated",
            detail="Administrator accounts must be managed from the server CLI.",
        )
    if target.is_enabled:
        changed = await queries.deactivate_non_admin_user(user_id=user_id)
        if changed is None:
            raise RuntimeError("user state changed concurrently")
        await AuthQuerier(connection).revoke_user_sessions(user_id=user_id)
        target = await queries.get_admin_user(user_id=user_id)
        if target is None:
            raise RuntimeError("deactivated user could not be read")
    return _response(target)
