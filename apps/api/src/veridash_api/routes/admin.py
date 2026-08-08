"""Administrator-only user management HTTP routes."""

from fastapi import APIRouter, status

from veridash_api.auth.dependencies import AdminMutationSession, AdminSession
from veridash_api.database import DatabaseConnection
from veridash_api.models import PROBLEM_RESPONSE, AdminUserResponse, CreateManagedUserRequest
from veridash_api.services.admin import create_user, deactivate_user, list_users

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get(
    "/users",
    response_model=list[AdminUserResponse],
    responses={
        401: {**PROBLEM_RESPONSE, "description": "Authentication required"},
        403: {**PROBLEM_RESPONSE, "description": "Administrator access required"},
    },
)
async def get_users(
    connection: DatabaseConnection,
    _session: AdminSession,
) -> list[AdminUserResponse]:
    return await list_users(connection)


@router.post(
    "/users",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {**PROBLEM_RESPONSE, "description": "Authentication required"},
        403: {**PROBLEM_RESPONSE, "description": "CSRF or administrator check failed"},
        409: {**PROBLEM_RESPONSE, "description": "Username or email already exists"},
        422: {**PROBLEM_RESPONSE, "description": "Invalid request"},
    },
)
async def post_user(
    payload: CreateManagedUserRequest,
    connection: DatabaseConnection,
    _session: AdminMutationSession,
) -> AdminUserResponse:
    return await create_user(
        connection,
        username=payload.username,
        email=payload.email,
        password=payload.password,
    )


@router.post(
    "/users/{user_id}/deactivate",
    response_model=AdminUserResponse,
    responses={
        401: {**PROBLEM_RESPONSE, "description": "Authentication required"},
        403: {**PROBLEM_RESPONSE, "description": "CSRF or administrator check failed"},
        404: {**PROBLEM_RESPONSE, "description": "User not found"},
        409: {**PROBLEM_RESPONSE, "description": "Administrator cannot be deactivated"},
        422: {**PROBLEM_RESPONSE, "description": "Invalid user ID"},
    },
)
async def post_deactivate_user(
    user_id: int,
    connection: DatabaseConnection,
    _session: AdminMutationSession,
) -> AdminUserResponse:
    return await deactivate_user(connection, user_id=user_id)
