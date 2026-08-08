import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import pytest
from veridash_analysis import BlobArtifactOutput, FileInput
from veridash_analysis.errors import AnalysisExecutionError
from veridash_analysis.transcription import TranscriptDocument, TranscriptSegment
from veridash_analysis.translation import (
    OPENAI_MODEL,
    ProviderBatchOutput,
    ProviderBatchResult,
    ProviderReference,
    ProviderTranslation,
    TranslateTranscriptModule,
    TranslationDocument,
    TranslationParameters,
    TranslationProvider,
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


class RecordingProvider:
    def __init__(self, translations: dict[int, str]) -> None:
        self.translations = translations
        self.calls: list[list[int]] = []

    def translate_batch(
        self,
        *,
        source_language: str,
        target_language: Literal["en"],
        segments: Sequence[TranscriptSegment],
    ) -> ProviderBatchResult:
        assert source_language == "no"
        assert target_language == "en"
        ordinals = [segment.ordinal for segment in segments]
        self.calls.append(ordinals)
        return ProviderBatchResult(
            output=ProviderBatchOutput(
                segments=[
                    ProviderTranslation(ordinal=ordinal, text=self.translations[ordinal])
                    for ordinal in ordinals
                ]
            ),
            reference=ProviderReference(
                response_id=f"resp-{len(self.calls)}",
                request_id=f"req-{len(self.calls)}",
                client_request_id=f"client-{len(self.calls)}",
                input_tokens=10,
                output_tokens=8,
            ),
        )


class UnexpectedProvider:
    def translate_batch(
        self,
        *,
        source_language: str,
        target_language: Literal["en"],
        segments: Sequence[TranscriptSegment],
    ) -> ProviderBatchResult:
        del source_language, target_language, segments
        raise AssertionError("provider must not be called")


def _transcript_input(
    tmp_path: Path,
    *,
    language: str = "no",
    texts: tuple[str, ...] = ("Første setning.", "Andre setning."),
) -> FileInput:
    document = TranscriptDocument(
        source_sha256="a" * 64,
        detected_language=language,
        detected_language_probability=0.98,
        media_duration_seconds=10,
        speech_duration_seconds=5,
        model_repository="test/model",
        model_revision="revision",
        inference_device="cpu",
        inference_compute_type="int8",
        segments=[
            TranscriptSegment(
                ordinal=ordinal,
                start_seconds=float(ordinal),
                end_seconds=float(ordinal) + 0.75,
                text=text,
            )
            for ordinal, text in enumerate(texts, start=1)
        ],
    )
    path = tmp_path / "transcript.json"
    encoded = document.model_dump_json().encode()
    path.write_bytes(encoded)
    return FileInput(
        path=path,
        sha256="b" * 64,
        size_bytes=len(encoded),
        media_type="application/json",
        schema_id="veridash.transcript",
        schema_version=1,
    )


def _run(
    tmp_path: Path,
    *,
    source: FileInput,
    provider: TranslationProvider,
    parameters: TranslationParameters | None = None,
) -> tuple[TranslationDocument, RecordingContext]:
    output = tmp_path / "output"
    output.mkdir()
    context = RecordingContext(output)
    result = TranslateTranscriptModule(provider=provider).run(
        context,
        {"transcribe.transcript": source},
        parameters or TranslationParameters(),
    )
    artifact = result.outputs["translation"]
    assert isinstance(artifact, BlobArtifactOutput)
    return TranslationDocument.model_validate_json(artifact.path.read_bytes()), context


def test_translation_is_an_automatic_translation_job_after_transcription() -> None:
    manifest = TranslateTranscriptModule.manifest

    assert manifest.automatic is True
    assert manifest.resource_class is ResourceClass.TRANSLATION
    assert manifest.dependencies == ("transcribe",)
    assert manifest.requires_source_file is False
    assert manifest.cacheable is False
    assert {item.name: item.value for item in manifest.fingerprints}["model"] == OPENAI_MODEL


def test_translation_preserves_timestamps_and_reports_batch_progress(tmp_path: Path) -> None:
    provider = RecordingProvider({1: "First sentence.", 2: "Second sentence."})
    source = _transcript_input(tmp_path)

    document, context = _run(
        tmp_path,
        source=source,
        provider=provider,
        parameters=TranslationParameters(batch_max_segments=1),
    )

    assert provider.calls == [[1], [2]]
    assert document.status == "translated"
    assert document.provider == "openai"
    assert document.model == OPENAI_MODEL
    assert document.source_transcript_sha256 == "b" * 64
    assert [segment.text for segment in document.segments] == [
        "First sentence.",
        "Second sentence.",
    ]
    assert document.segments[1].start_seconds == 2.0
    assert [reference.response_id for reference in document.provider_references] == [
        "resp-1",
        "resp-2",
    ]
    assert ("translating", 1, 2, "Translated batch 1 of 2") in context.progress
    assert context.progress[-1] == ("finalizing", 1, 1, "English translation ready")


def test_english_transcript_succeeds_without_provider_call(tmp_path: Path) -> None:
    source = _transcript_input(tmp_path, language="en", texts=("Already English.",))

    document, _context = _run(
        tmp_path,
        source=source,
        provider=UnexpectedProvider(),
    )

    assert document.status == "not_applicable"
    assert document.provider is None
    assert document.model is None
    assert document.provider_references == []
    assert [segment.text for segment in document.segments] == ["Already English."]


def test_empty_transcript_succeeds_without_provider_call(tmp_path: Path) -> None:
    source = _transcript_input(tmp_path, texts=())

    document, _context = _run(
        tmp_path,
        source=source,
        provider=UnexpectedProvider(),
    )

    assert document.status == "no_content"
    assert document.provider is None
    assert document.segments == []


def test_provider_must_return_exact_ordinals(tmp_path: Path) -> None:
    class IncompleteProvider:
        def translate_batch(
            self,
            *,
            source_language: str,
            target_language: Literal["en"],
            segments: Sequence[TranscriptSegment],
        ) -> ProviderBatchResult:
            del source_language, target_language, segments
            return ProviderBatchResult(
                output=ProviderBatchOutput(
                    segments=[ProviderTranslation(ordinal=2, text="Wrong ordinal")]
                ),
                reference=ProviderReference(
                    response_id="resp",
                    client_request_id="client",
                ),
            )

    output = tmp_path / "output"
    output.mkdir()
    with pytest.raises(AnalysisExecutionError) as raised:
        TranslateTranscriptModule(provider=IncompleteProvider()).run(
            RecordingContext(output),
            {"transcribe.transcript": _transcript_input(tmp_path)},
            TranslationParameters(),
        )

    assert raised.value.kind is ErrorKind.PROVIDER_UNAVAILABLE
    assert raised.value.retryable is True
    assert "Første" not in json.dumps(raised.value.diagnostic)


def test_missing_provider_key_is_a_safe_configuration_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    output = tmp_path / "output"
    output.mkdir()

    with pytest.raises(AnalysisExecutionError) as raised:
        TranslateTranscriptModule().run(
            RecordingContext(output),
            {"transcribe.transcript": _transcript_input(tmp_path)},
            TranslationParameters(),
        )

    assert raised.value.kind is ErrorKind.INTERNAL_BUG
    assert raised.value.public_message == "The translation provider is not configured."
