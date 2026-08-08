"""Explicit database connection boundaries for API requests."""

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


def get_database_engine(request: Request) -> AsyncEngine:
    """Read the application-owned engine without creating global DB state."""
    return cast(AsyncEngine, request.app.state.database_engine)


async def get_connection(
    engine: Annotated[AsyncEngine, Depends(get_database_engine)],
) -> AsyncIterator[AsyncConnection]:
    """Give one request one transaction, committed only after a successful response."""
    async with engine.begin() as connection:
        yield connection


DatabaseConnection = Annotated[AsyncConnection, Depends(get_connection)]
DatabaseEngine = Annotated[AsyncEngine, Depends(get_database_engine)]
