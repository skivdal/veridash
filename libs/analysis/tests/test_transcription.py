import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest
from veridash_analysis import BlobArtifactOutput, FileInput
from veridash_analysis.errors import AnalysisExecutionError
from veridash_analysis.transcription import (
    MODEL_RECEIPT_FILENAME,
    MODEL_REPOSITORY,
    MODEL_REVISION,
    LoadedBackend,
    TranscribeModule,
    TranscribeParameters,
    TranscriptDocument,
    TranscriptionBackend,
)
from veridash_core import ErrorKind, ResourceClass


class RecordingContext:
    attempt_number = 1

    def __init__(self, output_directory: Path) -> None:
        self.output_directory = output_directory
        self.progress: list[tuple[str, int | None, int | None, str | None]] = []

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
        self.progress.append((stage, completed, total, message))

    def is_canceled(self) -> bool:
        return False


@dataclass
class FakeWord:
    start: float
    end: float
    word: str
    probability: float


@dataclass
class FakeSegment:
    start: float
    end: float
    text: str
    avg_logprob: float = -0.2
    no_speech_prob: float = 0.05
    words: list[FakeWord] | None = None


@dataclass
class FakeInfo:
    language: str = "no"
    language_probability: float = 0.97
    duration: float = 12.5
    duration_after_vad: float = 8.2


class FakeBackend:
    def transcribe(
        self,
        audio: str,
        *,
        beam_size: int,
        vad_filter: bool,
        word_timestamps: bool,
        task: str,
        condition_on_previous_text: bool,
    ):
        del audio, beam_size, vad_filter, word_timestamps, task, condition_on_previous_text
        return iter(
            (
                FakeSegment(0.5, 2.0, " Første setning. "),
                FakeSegment(7.0, 10.0, "Andre setning."),
            )
        ), FakeInfo()


def _model_snapshot(path: Path) -> None:
    path.mkdir()
    for filename in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"):
        (path / filename).write_bytes(b"model")
    (path / MODEL_RECEIPT_FILENAME).write_text(
        json.dumps({"repository": MODEL_REPOSITORY, "revision": MODEL_REVISION}),
        encoding="utf-8",
    )


def test_transcription_is_an_automatic_gpu_job_with_model_provenance() -> None:
    manifest = TranscribeModule.manifest

    assert manifest.automatic is True
    assert manifest.resource_class is ResourceClass.GPU
    assert manifest.requires_source_file is True
    assert manifest.cacheable is False
    assert {item.name: item.value for item in manifest.fingerprints}["model_revision"] == (
        MODEL_REVISION
    )


def test_transcription_writes_timestamped_source_language_document(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    model = tmp_path / "model"
    _model_snapshot(model)
    output = tmp_path / "output"
    output.mkdir()
    context = RecordingContext(output)
    module = TranscribeModule(
        model_path=model,
        backend_loader=lambda _path, _device, _compute: LoadedBackend(
            backend=cast(TranscriptionBackend, FakeBackend()),
            device="cpu",
            compute_type="int8",
        ),
    )

    result = module.run(
        context,
        {
            "source_video": FileInput(
                path=source,
                sha256="a" * 64,
                size_bytes=5,
                media_type="video/mp4",
            )
        },
        TranscribeParameters(),
    )

    artifact = result.outputs["transcript"]
    assert isinstance(artifact, BlobArtifactOutput)
    document = TranscriptDocument.model_validate_json(artifact.path.read_bytes())
    assert document.detected_language == "no"
    assert [segment.text for segment in document.segments] == [
        "Første setning.",
        "Andre setning.",
    ]
    assert document.segments[1].start_seconds == 7.0
    assert context.progress[-1] == ("finalizing", 1, 1, "Transcript ready")
    assert any(
        stage == "transcribing" and completed == 10_000 and total == 12_500
        for stage, completed, total, _message in context.progress
    )


def test_transcription_fails_safely_when_pinned_model_is_absent(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    output = tmp_path / "output"
    output.mkdir()

    with pytest.raises(AnalysisExecutionError) as raised:
        TranscribeModule(model_path=tmp_path / "missing").run(
            RecordingContext(output),
            {
                "source_video": FileInput(
                    path=source,
                    sha256="a" * 64,
                    size_bytes=5,
                    media_type="video/mp4",
                )
            },
            TranscribeParameters(),
        )

    assert raised.value.kind is ErrorKind.INTERNAL_BUG
    assert raised.value.public_message == "The local transcription model is not installed."
