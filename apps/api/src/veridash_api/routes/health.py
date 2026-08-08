"""Process health endpoint."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Stable response returned by the process health endpoint."""

    status: Literal["ok"]
    service: Literal["veridash-api"]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report process health without asserting dependency readiness."""
    return HealthResponse(status="ok", service="veridash-api")
