import subprocess
from pathlib import Path

import pytest
from veridash_analysis import FileInput
from veridash_analysis.probe_media import ProbeMediaModule, ProbeMediaParameters


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


def test_probe_media_preserves_raw_ffprobe_document(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source-video"
    source_path.write_bytes(b"fixture")
    document = b'{"format":{"format_name":"mov,mp4","tags":{"location":"+1+2/"}},"streams":[]}'
    captured_command: tuple[str, ...] | None = None

    def fake_run(command: tuple[str, ...], **kwargs: object):
        nonlocal captured_command
        captured_command = command
        assert kwargs["timeout"] == 60
        return subprocess.CompletedProcess(command, 0, stdout=document, stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    context = RecordingContext()
    result = ProbeMediaModule().run(
        context,
        {
            "source_video": FileInput(
                path=source_path,
                sha256="a" * 64,
                size_bytes=7,
                media_type="video/mp4",
            )
        },
        ProbeMediaParameters(),
    )

    assert result.model_dump(mode="json") == {
        "outputs": {
            "result": {
                "type": "json",
                "value": {
                    "source_sha256": "a" * 64,
                    "probe": {
                        "format": {
                            "format_name": "mov,mp4",
                            "tags": {"location": "+1+2/"},
                        },
                        "streams": [],
                    },
                },
            },
        }
    }
    assert captured_command is not None
    assert captured_command[:5] == (
        "ffprobe",
        "-v",
        "error",
        "-protocol_whitelist",
        "file,crypto,data",
    )
    assert captured_command[-1] == str(source_path)
    assert context.progress == [("probing", 0, 1), ("probing", 1, 1)]
