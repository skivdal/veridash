import io

from veridash_analysis import (
    CHILD_MESSAGE_ADAPTER,
    ChildMessage,
    ChildRequest,
    ErrorMessage,
    ResultMessage,
)
from veridash_core import ErrorKind
from veridash_worker.child import run_child


def _messages(stream: io.StringIO) -> list[ChildMessage]:
    return [CHILD_MESSAGE_ADAPTER.validate_json(line) for line in stream.getvalue().splitlines()]


def test_synthetic_child_reports_progress_and_result() -> None:
    stream = io.StringIO()
    return_code = run_child(
        ChildRequest(
            module_id="synthetic_test",
            implementation_version="1.0.0",
            attempt_number=1,
            parameters={"steps": 2},
        ),
        stream,
    )

    messages = _messages(stream)
    assert return_code == 0
    assert [message.type for message in messages] == [
        "progress",
        "heartbeat",
        "progress",
        "heartbeat",
        "result",
    ]
    assert messages[-1] == ResultMessage(
        outputs={"result": {"steps_completed": 2, "deterministic_value": "synthetic:2"}}
    )


def test_synthetic_child_classifies_requested_transient_failure() -> None:
    stream = io.StringIO()
    return_code = run_child(
        ChildRequest(
            module_id="synthetic_test",
            implementation_version="1.0.0",
            attempt_number=1,
            parameters={"fail_attempts": 1},
        ),
        stream,
    )

    assert return_code == 2
    assert _messages(stream) == [
        ErrorMessage(
            error_kind=ErrorKind.TRANSIENT_INFRASTRUCTURE,
            public_message="The synthetic module requested a transient retry.",
            retryable=True,
            diagnostic="synthetic failure on attempt 1",
        )
    ]
