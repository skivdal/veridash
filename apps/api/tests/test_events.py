import json

from veridash_api.services.events import format_sse_event


def test_sse_event_is_replayable_and_newline_safe() -> None:
    encoded = format_sse_event(
        event_id=42,
        event_type="project-event",
        data={"message": "first\nsecond"},
    ).decode()

    assert encoded.startswith("id: 42\nevent: project-event\ndata: ")
    data_line = encoded.splitlines()[2]
    assert json.loads(data_line.removeprefix("data: ")) == {"message": "first\nsecond"}
    assert encoded.endswith("\n\n")
