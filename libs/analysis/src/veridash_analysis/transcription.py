"""Local, source-language speech transcription with timestamped provenance."""

import math
import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field
from veridash_core import ArtifactKind, ErrorKind, ResourceClass

from veridash_analysis.contracts import (
    BlobArtifactOutput,
    ImplementationFingerprint,
    ModuleManifest,
    ModuleResult,
    OutputSpec,
    ProgressStage,
    RunContext,
)
from veridash_analysis.errors import AnalysisExecutionError
from veridash_analysis.protocol import FileInput

MODEL_REPOSITORY = "Systran/faster-whisper-medium"
MODEL_REVISION = "08e178d48790749d25932bbc082711ddcfdfbc4f"
FASTER_WHISPER_VERSION = "1.2.1"
MODEL_RECEIPT_FILENAME = "veridash-model.json"
DEFAULT_MODEL_PATH = Path("/var/lib/veridash/models/faster-whisper-medium")
MAX_SEGMENTS = 100_000
MAX_TRANSCRIPT_CHARACTERS = 20_000_000
MAX_TRANSCRIPT_BYTES = 128 * 1024 * 1024


class TranscribeParameters(BaseModel):
    """Output-affecting inference parameters fixed in each logical request."""

    model_config = ConfigDict(extra="forbid")

    beam_size: int = Field(default=5, ge=1, le=20)
    vad_filter: bool = True
    word_timestamps: bool = False


class ModelReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repository: str
    revision: str


class TranscriptWord(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    text: str
    probability: float | None = Field(default=None, ge=0, le=1)


class TranscriptSegment(BaseModel):
    ordinal: int = Field(ge=1)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    text: str
    average_log_probability: float | None = None
    no_speech_probability: float | None = Field(default=None, ge=0, le=1)
    words: list[TranscriptWord] | None = None


class TranscriptDocument(BaseModel):
    schema_id: str = "veridash.transcript"
    schema_version: int = 1
    source_sha256: str
    detected_language: str
    detected_language_probability: float = Field(ge=0, le=1)
    media_duration_seconds: float = Field(ge=0)
    speech_duration_seconds: float = Field(ge=0)
    model_repository: str
    model_revision: str
    inference_device: str
    inference_compute_type: str
    segments: list[TranscriptSegment]


class BackendWord(Protocol):
    start: float
    end: float
    word: str
    probability: float


class BackendSegment(Protocol):
    start: float
    end: float
    text: str
    avg_logprob: float
    no_speech_prob: float
    words: list[BackendWord] | None


class BackendInfo(Protocol):
    language: str
    language_probability: float
    duration: float
    duration_after_vad: float


class TranscriptionBackend(Protocol):
    def transcribe(
        self,
        audio: str,
        *,
        beam_size: int,
        vad_filter: bool,
        word_timestamps: bool,
        task: str,
        condition_on_previous_text: bool,
    ) -> tuple[Iterable[BackendSegment], BackendInfo]: ...


class RuntimeEngine(Protocol):
    @property
    def device(self) -> str: ...

    @property
    def compute_type(self) -> str: ...


class BackendWithRuntime(Protocol):
    model: RuntimeEngine


@dataclass(frozen=True, slots=True)
class LoadedBackend:
    backend: TranscriptionBackend
    device: str
    compute_type: str


type BackendLoader = Callable[[Path, str, str], LoadedBackend]


class TranscribeModule:
    parameter_model: type[BaseModel] = TranscribeParameters
    manifest = ModuleManifest(
        module_id="transcribe",
        display_name="Transcription",
        version="1.0.0",
        result_schema_version=1,
        resource_class=ResourceClass.GPU,
        default_parameters=TranscribeParameters().model_dump(mode="json"),
        # CPU/GPU numerical paths can produce small decoding differences. Revisit
        # cacheability only after the target execution policy is fixed and tested.
        cacheable=False,
        requires_source_file=True,
        fingerprints=(
            ImplementationFingerprint(
                name="engine", value=f"faster-whisper-{FASTER_WHISPER_VERSION}"
            ),
            ImplementationFingerprint(name="model_repository", value=MODEL_REPOSITORY),
            ImplementationFingerprint(name="model_revision", value=MODEL_REVISION),
            ImplementationFingerprint(name="transcription_policy", value="source-language-v1"),
        ),
        progress_stages=(
            ProgressStage(
                key="loading_model",
                label="Loading transcription model",
                stall_after_seconds=900,
            ),
            ProgressStage(
                key="transcribing",
                label="Transcribing source speech",
                stall_after_seconds=600,
            ),
            ProgressStage(
                key="finalizing",
                label="Validating transcript",
                stall_after_seconds=120,
            ),
        ),
        outputs=(
            OutputSpec(
                name="transcript",
                kind=ArtifactKind.BLOB,
                media_type="application/json",
                schema_id="veridash.transcript",
                schema_version=1,
            ),
        ),
    )

    def __init__(
        self,
        *,
        model_path: Path | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        backend_loader: BackendLoader | None = None,
    ) -> None:
        self._model_path = model_path or Path(
            os.environ.get("VERIDASH_TRANSCRIPTION_MODEL_PATH", DEFAULT_MODEL_PATH)
        )
        self._device = device or os.environ.get("VERIDASH_TRANSCRIPTION_DEVICE", "auto")
        self._compute_type = compute_type or os.environ.get(
            "VERIDASH_TRANSCRIPTION_COMPUTE_TYPE", "default"
        )
        self._backend_loader = backend_loader or _load_faster_whisper

    def run(
        self,
        context: RunContext,
        inputs: Mapping[str, Any],
        parameters: BaseModel,
    ) -> ModuleResult:
        parsed = TranscribeParameters.model_validate(parameters)
        source = _source_input(inputs)
        context.report_progress(
            stage="loading_model",
            message="Validating the local transcription model",
        )
        _validate_model_snapshot(self._model_path)
        try:
            loaded = self._backend_loader(
                self._model_path,
                self._device,
                self._compute_type,
            )
        except (OSError, RuntimeError) as exception:
            raise _runtime_error(exception, while_loading=True) from exception

        context.report_progress(
            stage="transcribing",
            completed=0,
            total=1,
            message="Detecting language and transcribing speech",
        )
        try:
            raw_segments, info = loaded.backend.transcribe(
                str(source.path),
                beam_size=parsed.beam_size,
                vad_filter=parsed.vad_filter,
                word_timestamps=parsed.word_timestamps,
                task="transcribe",
                condition_on_previous_text=True,
            )
            duration_milliseconds = max(1, math.ceil(_finite_nonnegative(info.duration) * 1000))
            progress_interval = max(1_000, min(60_000, duration_milliseconds // 200))
            last_reported_milliseconds = 0
            segments: list[TranscriptSegment] = []
            character_count = 0
            for ordinal, raw_segment in enumerate(raw_segments, start=1):
                if ordinal > MAX_SEGMENTS:
                    raise AnalysisExecutionError(
                        kind=ErrorKind.RESOURCE_EXHAUSTED,
                        public_message="The transcript contains too many segments to store safely.",
                        retryable=False,
                        diagnostic=f"segment count exceeds {MAX_SEGMENTS}",
                    )
                segment = _normalize_segment(raw_segment, ordinal, parsed.word_timestamps)
                character_count += len(segment.text)
                if character_count > MAX_TRANSCRIPT_CHARACTERS:
                    raise AnalysisExecutionError(
                        kind=ErrorKind.RESOURCE_EXHAUSTED,
                        public_message="The transcript is too large to store safely.",
                        retryable=False,
                        diagnostic=f"transcript characters exceed {MAX_TRANSCRIPT_CHARACTERS}",
                    )
                segments.append(segment)
                completed = min(
                    duration_milliseconds,
                    max(0, math.floor(segment.end_seconds * 1000)),
                )
                if completed - last_reported_milliseconds >= progress_interval:
                    context.report_progress(
                        stage="transcribing",
                        completed=completed,
                        total=duration_milliseconds,
                        message=f"Transcribed {ordinal} segments",
                    )
                    last_reported_milliseconds = completed
        except AnalysisExecutionError:
            raise
        except (OSError, RuntimeError, ValueError) as exception:
            raise _runtime_error(exception, while_loading=False) from exception

        context.report_progress(
            stage="transcribing",
            completed=duration_milliseconds,
            total=duration_milliseconds,
            message=f"Transcribed {len(segments)} segments",
        )
        context.report_progress(
            stage="finalizing",
            completed=0,
            total=1,
            message="Writing the timestamped transcript",
        )
        document = TranscriptDocument(
            source_sha256=source.sha256,
            detected_language=info.language,
            detected_language_probability=_probability(info.language_probability),
            media_duration_seconds=_finite_nonnegative(info.duration),
            speech_duration_seconds=_finite_nonnegative(info.duration_after_vad),
            model_repository=MODEL_REPOSITORY,
            model_revision=MODEL_REVISION,
            inference_device=loaded.device,
            inference_compute_type=loaded.compute_type,
            segments=segments,
        )
        output_path = context.output_directory / "transcript.json"
        encoded = document.model_dump_json(exclude_none=True).encode("utf-8")
        if len(encoded) > MAX_TRANSCRIPT_BYTES:
            raise AnalysisExecutionError(
                kind=ErrorKind.RESOURCE_EXHAUSTED,
                public_message="The transcript is too large to store safely.",
                retryable=False,
                diagnostic=f"transcript bytes: {len(encoded)}",
            )
        output_path.write_bytes(encoded)
        context.report_progress(
            stage="finalizing",
            completed=1,
            total=1,
            message="Transcript ready",
        )
        return ModuleResult(outputs={"transcript": BlobArtifactOutput(path=output_path)})


def _source_input(inputs: Mapping[str, Any]) -> FileInput:
    try:
        return FileInput.model_validate(inputs["source_video"])
    except (KeyError, ValueError) as exception:
        raise AnalysisExecutionError(
            kind=ErrorKind.INVALID_INPUT,
            public_message="The source video is unavailable for transcription.",
            retryable=False,
            diagnostic=str(exception),
        ) from exception


def _validate_model_snapshot(model_path: Path) -> None:
    receipt_path = model_path / MODEL_RECEIPT_FILENAME
    try:
        receipt = ModelReceipt.model_validate_json(receipt_path.read_bytes())
    except (FileNotFoundError, OSError, ValueError) as exception:
        raise AnalysisExecutionError(
            kind=ErrorKind.INTERNAL_BUG,
            public_message="The local transcription model is not installed.",
            retryable=False,
            diagnostic=f"invalid model receipt at {receipt_path}: {exception}",
        ) from exception
    if receipt.repository != MODEL_REPOSITORY or receipt.revision != MODEL_REVISION:
        raise AnalysisExecutionError(
            kind=ErrorKind.INTERNAL_BUG,
            public_message="The installed transcription model has the wrong version.",
            retryable=False,
            diagnostic=f"model receipt does not identify {MODEL_REPOSITORY}@{MODEL_REVISION}",
        )
    for filename in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"):
        path = model_path / filename
        if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
            raise AnalysisExecutionError(
                kind=ErrorKind.INTERNAL_BUG,
                public_message="The local transcription model is incomplete.",
                retryable=False,
                diagnostic=f"missing or invalid model file: {filename}",
            )


def _normalize_segment(
    segment: BackendSegment,
    ordinal: int,
    include_words: bool,
) -> TranscriptSegment:
    start = _finite_nonnegative(segment.start)
    end = _finite_nonnegative(segment.end)
    if end < start:
        raise ValueError("transcript segment ends before it starts")
    words = None
    if include_words and segment.words is not None:
        words = [
            TranscriptWord(
                start_seconds=_finite_nonnegative(word.start),
                end_seconds=_finite_nonnegative(word.end),
                text=word.word,
                probability=_probability(word.probability),
            )
            for word in segment.words
        ]
    return TranscriptSegment(
        ordinal=ordinal,
        start_seconds=start,
        end_seconds=end,
        text=segment.text.strip(),
        average_log_probability=_finite_or_none(segment.avg_logprob),
        no_speech_probability=_probability(segment.no_speech_prob),
        words=words,
    )


def _finite_nonnegative(value: float) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError("transcription runtime returned an invalid nonnegative number")
    return round(parsed, 6)


def _finite_or_none(value: float) -> float | None:
    parsed = float(value)
    return round(parsed, 6) if math.isfinite(parsed) else None


def _probability(value: float) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("transcription runtime returned an invalid probability")
    return round(min(1.0, max(0.0, parsed)), 6)


def _runtime_error(
    exception: OSError | RuntimeError | ValueError, *, while_loading: bool
) -> AnalysisExecutionError:
    diagnostic = str(exception)[-10_000:]
    lowered = diagnostic.lower()
    if "out of memory" in lowered or "failed to allocate" in lowered:
        return AnalysisExecutionError(
            kind=ErrorKind.RESOURCE_EXHAUSTED,
            public_message="The transcription worker ran out of memory.",
            retryable=True,
            diagnostic=diagnostic,
        )
    if while_loading or any(token in lowered for token in ("cuda", "cudnn", "cublas")):
        return AnalysisExecutionError(
            kind=ErrorKind.RESOURCE_EXHAUSTED,
            public_message="The configured transcription runtime is unavailable.",
            retryable=False,
            diagnostic=diagnostic,
        )
    return AnalysisExecutionError(
        kind=ErrorKind.INVALID_INPUT,
        public_message="Speech could not be transcribed from this video.",
        retryable=False,
        diagnostic=diagnostic,
    )


def _load_faster_whisper(model_path: Path, device: str, compute_type: str) -> LoadedBackend:
    try:
        from faster_whisper import WhisperModel  # pyright: ignore[reportMissingTypeStubs]
    except ImportError as exception:
        raise RuntimeError("faster-whisper is not installed") from exception

    backend = WhisperModel(
        str(model_path),
        device=device,
        compute_type=compute_type,
        local_files_only=True,
        num_workers=1,
    )
    runtime = cast(BackendWithRuntime, cast(object, backend)).model
    return LoadedBackend(
        backend=cast(TranscriptionBackend, cast(object, backend)),
        device=runtime.device,
        compute_type=runtime.compute_type,
    )
