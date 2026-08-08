from pathlib import Path

import pytest
from pydantic import ValidationError
from veridash_analysis.protocol import FileInput
from veridash_analysis.stitching import (
    StitchFramesModule,
    StitchFramesParameters,
)


class RecordingContext:
    attempt_number = 1

    def __init__(self, output_directory: Path) -> None:
        self.output_directory = output_directory
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
        self.progress.append((stage, completed, total))

    def is_canceled(self) -> bool:
        return False


def _jpeg(path: Path, content: bytes) -> FileInput:
    encoded = b"\xff\xd8" + content + b"\xff\xd9"
    path.write_bytes(encoded)
    return FileInput(
        path=path,
        sha256=(content.hex() * 64)[:64],
        size_bytes=len(encoded),
        media_type="image/jpeg",
        schema_id="veridash.keyframe.jpeg",
        schema_version=1,
    )


def test_stitch_parameters_preserve_order_and_reject_duplicates() -> None:
    parameters = StitchFramesParameters(selected_output_names=["frames_000002", "frames_000001"])

    assert parameters.selected_output_names == ["frames_000002", "frames_000001"]
    with pytest.raises(ValidationError, match="unique"):
        StitchFramesParameters(selected_output_names=["frames_000001", "frames_000001"])


def test_stitch_module_uses_only_selected_frames_in_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _jpeg(tmp_path / "first.jpg", b"first")
    second = _jpeg(tmp_path / "second.jpg", b"second")
    ignored = _jpeg(tmp_path / "ignored.jpg", b"ignored")
    stitched_paths: list[Path] = []

    def fake_stitch(paths: list[Path], output_path: Path) -> tuple[int, int]:
        stitched_paths.extend(paths)
        output_path.write_bytes(b"\xff\xd8panorama\xff\xd9")
        return 640, 240

    monkeypatch.setattr("veridash_analysis.stitching._stitch", fake_stitch)
    context = RecordingContext(tmp_path)
    result = StitchFramesModule().run(
        context,
        {
            "extract_keyframes.frames_000001": first,
            "extract_keyframes.frames_000002": second,
            "extract_keyframes.frames_000003": ignored,
        },
        StitchFramesParameters(selected_output_names=["frames_000002", "frames_000001"]),
    )

    assert stitched_paths == [second.path, first.path]
    assert set(result.outputs) == {"result", "panorama"}
    structured = result.outputs["result"]
    assert structured.type == "json"
    assert structured.value == {
        "algorithm": "opencv_panorama",
        "width": 640,
        "height": 240,
        "source_frames": [
            {"output_name": "frames_000002", "sha256": second.sha256},
            {"output_name": "frames_000001", "sha256": first.sha256},
        ],
    }
    assert context.progress[-1] == ("encoding", 1, 1)
