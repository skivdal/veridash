"""Safe, consistent HTTP problem responses."""

import logging
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

LOGGER = logging.getLogger(__name__)
PROBLEM_MEDIA_TYPE = "application/problem+json"


@dataclass
class ApiProblem(Exception):
    """An expected API error whose detail is safe to show to a user."""

    status: int
    code: str
    title: str
    detail: str
    headers: dict[str, str] | None = None


def _response(problem: ApiProblem, *, diagnostic_id: str | None = None) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"urn:veridash:problem:{problem.code}",
        "title": problem.title,
        "status": problem.status,
        "detail": problem.detail,
        "code": problem.code,
    }
    if diagnostic_id is not None:
        body["diagnosticId"] = diagnostic_id
    return JSONResponse(
        body,
        status_code=problem.status,
        media_type=PROBLEM_MEDIA_TYPE,
        headers=problem.headers,
    )


def install_error_handlers(app: FastAPI) -> None:
    """Install handlers that never expose request bodies or exception internals."""

    async def handle_api_problem(_request: Request, exception: Exception) -> JSONResponse:
        if not isinstance(exception, ApiProblem):
            raise TypeError("ApiProblem handler received a different exception")
        return _response(exception)

    async def _handle_validation_error(
        _request: Request,
        exception: Exception,
    ) -> JSONResponse:
        if not isinstance(exception, RequestValidationError):
            raise TypeError("validation handler received a different exception")
        return _response(
            ApiProblem(
                status=422,
                code="invalid_request",
                title="Invalid request",
                detail="One or more request fields are invalid.",
            )
        )

    async def handle_unexpected_error(request: Request, exception: Exception) -> JSONResponse:
        diagnostic_id = str(uuid4())
        LOGGER.exception(
            "Unhandled API error",
            extra={"diagnostic_id": diagnostic_id, "path": request.url.path},
            exc_info=exception,
        )
        return _response(
            ApiProblem(
                status=500,
                code="internal_error",
                title="Internal server error",
                detail="The request could not be completed.",
            ),
            diagnostic_id=diagnostic_id,
        )

    app.add_exception_handler(ApiProblem, handle_api_problem)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
