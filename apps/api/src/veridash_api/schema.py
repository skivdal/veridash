"""Database schema compatibility boundary for the API process."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

REQUIRED_DATABASE_SCHEMA_VERSION = "20260808200000"


class DatabaseSchemaMismatchError(RuntimeError):
    """Raised when application code and the migrated database do not match."""


async def database_schema_is_current(connection: AsyncConnection) -> bool:
    result = await connection.execute(
        text(
            """
            SELECT COALESCE(max(version) = :required_version, FALSE)
            FROM schema_migrations
            """
        ),
        {"required_version": REQUIRED_DATABASE_SCHEMA_VERSION},
    )
    return bool(result.scalar_one())


async def require_current_database_schema(connection: AsyncConnection) -> None:
    if not await database_schema_is_current(connection):
        raise DatabaseSchemaMismatchError(
            "database schema is not current; run `uv run poe db:up` before starting the API"
        )
