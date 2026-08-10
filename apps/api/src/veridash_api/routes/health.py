"""Process liveness and dependency-aware readiness endpoints."""

import logging
import shutil
from typing import Literal, cast

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from veridash_storage import UploadBlobStore

from veridash_api.auth.dependencies import ApiSettings
from veridash_api.database import DatabaseEngine
from veridash_api.schema import database_schema_is_current

router = APIRouter(tags=["system"])
LOGGER = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    """Stable response returned by the process health endpoint."""

    status: Literal["ok"]
    service: Literal["veridash-api"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "unavailable"]
    service: Literal["veridash-api"]
    dependencies: dict[str, Literal["ready", "unavailable"]]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report process health without asserting dependency readiness."""
    return HealthResponse(status="ok", service="veridash-api")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse, "description": "Dependency unavailable"}},
)
async def ready(
    request: Request,
    engine: DatabaseEngine,
    settings: ApiSettings,
) -> ReadinessResponse | JSONResponse:
    """Report whether required database, storage, and media-tool dependencies work."""
    dependencies: dict[str, Literal["ready", "unavailable"]] = {
        "database": "ready",
        "database_schema": "ready",
        "blob_storage": "ready",
        "ffprobe": "ready",
    }
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            if not await database_schema_is_current(connection):
                dependencies["database_schema"] = "unavailable"
                LOGGER.error("readiness database-schema check failed")
    except Exception:
        dependencies["database"] = "unavailable"
        dependencies["database_schema"] = "unavailable"
        LOGGER.exception("readiness database check failed")

    try:
        blob_store = cast(UploadBlobStore, request.app.state.blob_store)
        blob_store.check_ready()
    except Exception:
        dependencies["blob_storage"] = "unavailable"
        LOGGER.exception("readiness blob-storage check failed")

    if shutil.which(settings.ffprobe_executable) is None:
        dependencies["ffprobe"] = "unavailable"
        LOGGER.error("readiness media-tool check failed")

    response = ReadinessResponse(
        status=(
            "ready" if all(value == "ready" for value in dependencies.values()) else "unavailable"
        ),
        service="veridash-api",
        dependencies=dependencies,
    )
    if response.status == "ready":
        return response
    return JSONResponse(status_code=503, content=response.model_dump(mode="json"))
