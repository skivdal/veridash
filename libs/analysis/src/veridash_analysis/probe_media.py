"""Deterministic FFprobe-backed source inspection."""

import json
import subprocess
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter
from veridash_core import ArtifactKind, ErrorKind, ResourceClass

from veridash_analysis.contracts import (
    ImplementationFingerprint,
    ModuleManifest,
    OutputSpec,
    ProgressStage,
    RunContext,
)
from veridash_analysis.errors import AnalysisExecutionError
from veridash_analysis.protocol import FileInput

PROBE_DOCUMENT = TypeAdapter(dict[str, JsonValue])
MAX_PROBE_OUTPUT_BYTES = 512 * 1024


class ProbeMediaParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProbeMediaResult(BaseModel):
    source_sha256: str
    probe: dict[str, JsonValue]


class ProbeMediaModule:
    parameter_model: type[BaseModel] = ProbeMediaParameters
    manifest = ModuleManifest(
        module_id="probe_media",
        display_name="Media metadata",
        version="1.0.0",
        result_schema_version=1,
        resource_class=ResourceClass.CPU,
        default_parameters={},
        # Enable cross-job reuse only after the deployment pins an exact FFmpeg build.
        cacheable=False,
        requires_source_file=True,
        fingerprints=(
            ImplementationFingerprint(name="ffprobe_arguments", value="show-all-v1"),
            ImplementationFingerprint(name="ffprobe_binary", value="deployment-unpinned"),
        ),
        progress_stages=(
            ProgressStage(key="probing", label="Reading media metadata", stall_after_seconds=60),
        ),
        outputs=(
            OutputSpec(
                name="result",
                kind=ArtifactKind.JSON,
                media_type="application/json",
                schema_id="veridash.probe_media.raw",
                schema_version=1,
            ),
        ),
    )

    def run(
        self,
        context: RunContext,
        inputs: Mapping[str, Any],
        parameters: BaseModel,
    ) -> BaseModel:
        ProbeMediaParameters.model_validate(parameters)
        try:
            source = FileInput.model_validate(inputs["source_video"])
        except (KeyError, ValueError) as exception:
            raise AnalysisExecutionError(
                kind=ErrorKind.INVALID_INPUT,
                public_message="The source video is unavailable for metadata analysis.",
                retryable=False,
                diagnostic=str(exception),
            ) from exception

        context.report_progress(
            stage="probing",
            completed=0,
            total=1,
            message="Reading container and stream metadata",
        )
        try:
            completed = subprocess.run(
                (
                    "ffprobe",
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    "file,crypto,data",
                    "-show_format",
                    "-show_streams",
                    "-show_chapters",
                    "-of",
                    "json",
                    str(source.path),
                ),
                check=False,
                capture_output=True,
                timeout=60,
            )
        except FileNotFoundError as exception:
            raise AnalysisExecutionError(
                kind=ErrorKind.INTERNAL_BUG,
                public_message="The media metadata tool is not installed.",
                retryable=False,
                diagnostic=str(exception),
            ) from exception
        except subprocess.TimeoutExpired as exception:
            raise AnalysisExecutionError(
                kind=ErrorKind.STALLED,
                public_message="Reading media metadata took too long.",
                retryable=True,
                diagnostic=str(exception),
            ) from exception
        if completed.returncode != 0:
            diagnostic = completed.stderr.decode(errors="replace")[-10_000:]
            raise AnalysisExecutionError(
                kind=ErrorKind.INVALID_INPUT,
                public_message="The source video metadata could not be read.",
                retryable=False,
                diagnostic=diagnostic,
            )
        if len(completed.stdout) > MAX_PROBE_OUTPUT_BYTES:
            raise AnalysisExecutionError(
                kind=ErrorKind.RESOURCE_EXHAUSTED,
                public_message="The source contains too much embedded metadata to display safely.",
                retryable=False,
                diagnostic=f"ffprobe output was {len(completed.stdout)} bytes",
            )
        try:
            probe = PROBE_DOCUMENT.validate_python(json.loads(completed.stdout))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exception:
            raise AnalysisExecutionError(
                kind=ErrorKind.INTERNAL_BUG,
                public_message="The media metadata tool returned an invalid result.",
                retryable=False,
                diagnostic=str(exception),
            ) from exception
        context.report_progress(
            stage="probing",
            completed=1,
            total=1,
            message="Media metadata ready",
        )
        return ProbeMediaResult(source_sha256=source.sha256, probe=probe)
