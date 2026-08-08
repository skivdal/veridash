from pathlib import Path

import pytest
from veridash_analysis import BlobArtifactOutput, FileInput, JsonArtifactOutput
from veridash_analysis.keyframes import (
    ExtractKeyframesModule,
    ExtractKeyframesParameters,
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
        del message
        self.progress.append((stage, completed, total))

    def is_canceled(self) -> bool:
        return False


def test_keyframe_module_returns_timestamped_bounded_collection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source.mp4"
    source_path.write_bytes(b"source")
    output_directory = tmp_path / "outputs"
    output_directory.mkdir()
    captured_interval: float | None = None

    def fake_probe(_path: Path) -> float:
        return 1_200.0

    monkeypatch.setattr("veridash_analysis.keyframes._probe_duration", fake_probe)

    def fake_extract(
        _context: object,
        _source_path: Path,
        target: Path,
        *,
        duration_seconds: float,
        interval_seconds: float,
        max_frames: int,
        jpeg_quality: int,
    ) -> list[float]:
        nonlocal captured_interval
        del duration_seconds, max_frames, jpeg_quality
        captured_interval = interval_seconds
        (target / "frame_000001.jpg").write_bytes(b"\xff\xd8frame\xff\xd9")
        (target / "frame_000002.jpg").write_bytes(b"\xff\xd8frame\xff\xd9")
        return [0.0, interval_seconds]

    monkeypatch.setattr("veridash_analysis.keyframes._extract_frames", fake_extract)
    result = ExtractKeyframesModule().run(
        RecordingContext(output_directory),
        {
            "source_video": FileInput(
                path=source_path,
                sha256="a" * 64,
                size_bytes=6,
                media_type="video/mp4",
            )
        },
        ExtractKeyframesParameters(max_frames=600),
    )

    assert captured_interval == 2.0
    assert isinstance(result.outputs["index"], JsonArtifactOutput)
    assert isinstance(result.outputs["frames_000001"], BlobArtifactOutput)
    assert isinstance(result.outputs["frames_000002"], BlobArtifactOutput)
