from pathlib import Path

import pytest
from pydantic import ValidationError
from veridash_analysis import CHILD_MESSAGE_ADAPTER, ChildRequest, ProgressMessage


def test_child_request_rejects_orchestrator_capabilities() -> None:
    with pytest.raises(ValidationError):
        ChildRequest.model_validate(
            {
                "protocol_version": 2,
                "module_id": "synthetic_test",
                "implementation_version": "1.0.0",
                "attempt_number": 1,
                "output_directory": Path("/tmp/veridash-output"),
                "parameters": {},
                "database_url": "postgresql://should-not-be-here",
            }
        )


def test_child_messages_use_a_discriminated_closed_schema() -> None:
    parsed = CHILD_MESSAGE_ADAPTER.validate_json(
        b'{"type":"progress","stage":"working","completed":1,"total":2}'
    )
    assert parsed == ProgressMessage(stage="working", completed=1, total=2)

    with pytest.raises(ValidationError):
        CHILD_MESSAGE_ADAPTER.validate_json(b'{"type":"progress","stage":"working","extra":1}')
