"""Single-attempt child process with no database or orchestration authority."""

import contextlib
import sys
import traceback
from typing import TextIO

from pydantic import ValidationError
from veridash_analysis import (
    AnalysisExecutionError,
    ChildRequest,
    ErrorMessage,
    HeartbeatMessage,
    ProgressMessage,
    ResultMessage,
)
from veridash_analysis.modules import get_builtin_module
from veridash_core import ErrorKind

MAX_REQUEST_BYTES = 1024 * 1024
MAX_DIAGNOSTIC_CHARACTERS = 10_000


class ChildRunContext:
    def __init__(self, *, attempt_number: int, protocol_stream: TextIO) -> None:
        self._attempt_number = attempt_number
        self._protocol_stream = protocol_stream

    @property
    def attempt_number(self) -> int:
        return self._attempt_number

    def heartbeat(self) -> None:
        self._emit(HeartbeatMessage())

    def report_progress(
        self,
        *,
        stage: str,
        completed: int | None = None,
        total: int | None = None,
        message: str | None = None,
    ) -> None:
        self._emit(
            ProgressMessage(
                stage=stage,
                completed=completed,
                total=total,
                message=message,
            )
        )

    def is_canceled(self) -> bool:
        return False

    def _emit(self, message: HeartbeatMessage | ProgressMessage) -> None:
        self._protocol_stream.write(message.model_dump_json() + "\n")
        self._protocol_stream.flush()


def run_child(request: ChildRequest, protocol_stream: TextIO) -> int:
    try:
        module = get_builtin_module(request.module_id)
        if module.manifest.version != request.implementation_version:
            raise AnalysisExecutionError(
                kind=ErrorKind.INVALID_INPUT,
                public_message="The requested analysis version is not installed.",
                retryable=False,
                diagnostic=(
                    f"requested {request.implementation_version}, "
                    f"installed {module.manifest.version}"
                ),
            )
        parameters = module.parameter_model.model_validate(request.parameters)
        context = ChildRunContext(
            attempt_number=request.attempt_number,
            protocol_stream=protocol_stream,
        )
        with contextlib.redirect_stdout(sys.stderr):
            result = module.run(context, {}, parameters)
        if len(module.manifest.outputs) != 1:
            raise RuntimeError("single-result child adapter requires exactly one output")
        output_name = module.manifest.outputs[0].name
        protocol_stream.write(
            ResultMessage(outputs={output_name: result.model_dump(mode="json")}).model_dump_json()
            + "\n"
        )
        protocol_stream.flush()
        return 0
    except AnalysisExecutionError as exception:
        protocol_stream.write(
            ErrorMessage(
                error_kind=exception.kind,
                public_message=exception.public_message,
                retryable=exception.retryable,
                diagnostic=exception.diagnostic,
            ).model_dump_json()
            + "\n"
        )
        protocol_stream.flush()
        return 2
    except Exception:
        diagnostic = traceback.format_exc()[-MAX_DIAGNOSTIC_CHARACTERS:]
        protocol_stream.write(
            ErrorMessage(
                error_kind=ErrorKind.INTERNAL_BUG,
                public_message="The analysis stopped because of an internal error.",
                retryable=False,
                diagnostic=diagnostic,
            ).model_dump_json()
            + "\n"
        )
        protocol_stream.flush()
        return 3


def main() -> None:
    raw_request = sys.stdin.buffer.readline(MAX_REQUEST_BYTES + 1)
    if len(raw_request) > MAX_REQUEST_BYTES:
        raise SystemExit("child request exceeds protocol limit")
    try:
        request = ChildRequest.model_validate_json(raw_request)
    except (ValidationError, ValueError):
        raise SystemExit("invalid child request") from None
    raise SystemExit(run_child(request, sys.stdout))


if __name__ == "__main__":
    main()
