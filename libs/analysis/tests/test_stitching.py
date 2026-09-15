import hashlib
import importlib
from pathlib import Path

import pytest
from pydantic import ValidationError
from veridash_analysis.errors import AnalysisExecutionError
from veridash_analysis.protocol import FileInput
from veridash_analysis.stitching import (
    StitchFramesModule,
    StitchFramesParameters,
)
from veridash_core import ErrorKind


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


def test_stitch_module_with_installed_opencv(tmp_path: Path) -> None:
    """Exercise the pinned wheel, including its distinct package/runtime versions."""
    cv2 = importlib.import_module("cv2")
    np = importlib.import_module("numpy")
    scene = np.random.default_rng(0).integers(0, 256, (480, 960, 3), dtype=np.uint8)
    inputs: dict[str, FileInput] = {}
    names = ["frames_000001", "frames_000002"]
    for name, left in zip(names, [0, 240], strict=True):
        path = tmp_path / f"{name}.jpg"
        assert cv2.imwrite(str(path), scene[:, left : left + 640])
        encoded = path.read_bytes()
        inputs[f"extract_keyframes.{name}"] = FileInput(
            path=path,
            sha256=hashlib.sha256(encoded).hexdigest(),
            size_bytes=len(encoded),
            media_type="image/jpeg",
            schema_id="veridash.keyframe.jpeg",
            schema_version=1,
        )

    context = RecordingContext(tmp_path)
    result = StitchFramesModule().run(
        context, inputs, StitchFramesParameters(selected_output_names=names)
    )

    panorama = result.outputs["panorama"]
    assert panorama.type == "blob"
    decoded = cv2.imread(str(panorama.path))
    assert decoded is not None
    height, width = decoded.shape[:2]
    assert width > 800  # Both overlapping inputs contribute to the panorama.
    assert height > 400
    structured = result.outputs["result"]
    assert structured.type == "json"
    assert structured.value == {
        "algorithm": "opencv_panorama",
        "width": width,
        "height": height,
        "source_frames": [
            {"output_name": name, "sha256": inputs[f"extract_keyframes.{name}"].sha256}
            for name in names
        ],
    }
    assert context.progress[-1] == ("encoding", 1, 1)


def test_stitch_rejects_a_different_opencv_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def mismatched_version(name: str) -> str:
        assert name == "opencv-python-headless"
        return "4.11.0.86"

    monkeypatch.setattr("importlib.metadata.version", mismatched_version)
    first = _jpeg(tmp_path / "first.jpg", b"first")
    second = _jpeg(tmp_path / "second.jpg", b"second")

    with pytest.raises(AnalysisExecutionError) as raised:
        StitchFramesModule().run(
            RecordingContext(tmp_path),
            {
                "extract_keyframes.frames_000001": first,
                "extract_keyframes.frames_000002": second,
            },
            StitchFramesParameters(selected_output_names=["frames_000001", "frames_000002"]),
        )

    assert raised.value.kind == ErrorKind.INTERNAL_BUG
    assert "server's OpenCV installation" in raised.value.public_message
    assert raised.value.diagnostic is not None
    assert "expected opencv-python-headless 4.12.0.88, found 4.11.0.86" in raised.value.diagnostic
