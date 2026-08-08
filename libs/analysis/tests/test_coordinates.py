from pathlib import Path

from veridash_analysis import JsonInput
from veridash_analysis.coordinates import (
    ExtractCoordinatesModule,
    ExtractCoordinatesParameters,
    extract_coordinate_candidates,
    parse_decimal_iso_6709,
    summarize_candidates,
)


class RecordingContext:
    output_directory = Path("/tmp/veridash-test-output")
    attempt_number = 1

    def __init__(self) -> None:
        self.progress: list[tuple[str, int | None, int | None]] = []

    def heartbeat(self) -> None:
        pass

    def report_progress(
        self,
        *,
        stage: str,
        completed: int | None = None,
        total: int | None = None,
        message: str | None = None,
    ) -> None:
        del message
        self.progress.append((stage, completed, total))

    def is_canceled(self) -> bool:
        return False


def test_decimal_iso_6709_parser_preserves_sign_and_optional_altitude() -> None:
    assert parse_decimal_iso_6709("+55.6058+013.0007+12.5/") == (
        55.6058,
        13.0007,
        12.5,
    )
    assert parse_decimal_iso_6709("-33.8688+151.2093/") == (-33.8688, 151.2093, None)
    assert parse_decimal_iso_6709("55.6058,13.0007") is None
    assert parse_decimal_iso_6709("+91.0+013.0/") is None


def test_candidate_summary_does_not_choose_between_conflicting_tags() -> None:
    candidates = extract_coordinate_candidates(
        {
            "format": {
                "tags": {
                    "location": "+55.6058+013.0007/",
                    "com.apple.quicktime.location.ISO6709": "+59.9139+010.7522/",
                }
            },
            "streams": [],
        }
    )

    result = summarize_candidates(candidates)

    assert result.status == "ambiguous"
    assert result.latitude is None
    assert len(result.candidates) == 2


def test_coordinate_module_returns_a_truthful_absence_result() -> None:
    context = RecordingContext()
    result = ExtractCoordinatesModule().run(
        context,
        {
            "probe_media.result": JsonInput(
                sha256="a" * 64,
                size_bytes=2,
                media_type="application/json",
                schema_id="veridash.probe_media.raw",
                schema_version=1,
                value={
                    "source_sha256": "b" * 64,
                    "probe": {"format": {"format_name": "mov,mp4"}, "streams": []},
                },
            )
        },
        ExtractCoordinatesParameters(),
    )

    assert result.model_dump(mode="json")["outputs"]["result"]["value"] == {
        "status": "not_found",
        "latitude": None,
        "longitude": None,
        "altitude_meters": None,
        "candidates": [],
    }
    assert context.progress == [("inspecting", 0, 1), ("inspecting", 1, 1)]
