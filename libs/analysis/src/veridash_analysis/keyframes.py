"""Deterministic, bounded FFmpeg keyframe sampling for frame review."""

import json
import math
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from veridash_core import ArtifactKind, ErrorKind, ResourceClass

from veridash_analysis.contracts import (
    BlobArtifactOutput,
    ImplementationFingerprint,
    JsonArtifactOutput,
    ModuleManifest,
    ModuleResult,
    OutputSpec,
    ProgressStage,
    RunContext,
)
from veridash_analysis.errors import AnalysisExecutionError
from veridash_analysis.fingerprints import (
    UNPINNED_FFMPEG_FINGERPRINT,
    bind_ffmpeg_fingerprint,
)
from veridash_analysis.protocol import FileInput

SHOWINFO_TIMESTAMP = re.compile(r"\bn:\s*\d+\s+pts:\s*-?\d+\s+pts_time:([-+0-9.eE]+)")
PROGRESS_TIME_US = re.compile(r"^out_time_us=(\d+)$")
FRAME_FILENAME = re.compile(r"^frame_(\d{6})\.jpg$")
MAX_DURATION_OUTPUT_BYTES = 64 * 1024
MAX_FRAME_BYTES = 25 * 1024 * 1024
MAX_TOTAL_FRAME_BYTES = 2 * 1024 * 1024 * 1024


class ExtractKeyframesParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interval_seconds: float = Field(default=1.0, gt=0, le=3600)
    max_frames: int = Field(default=600, ge=1, le=3600)
    jpeg_quality: int = Field(default=3, ge=2, le=31)


class KeyframeIndexItem(BaseModel):
    output_name: str
    ordinal: int = Field(ge=1)
    timestamp_seconds: float = Field(ge=0)


class KeyframeIndex(BaseModel):
    source_sha256: str
    requested_interval_seconds: float
    effective_interval_seconds: float
    frames: list[KeyframeIndexItem]


class ExtractKeyframesModule:
    parameter_model: type[BaseModel] = ExtractKeyframesParameters
    manifest = ModuleManifest(
        module_id="extract_keyframes",
        display_name="Frames",
        version="1.0.0",
        result_schema_version=1,
        resource_class=ResourceClass.CPU,
        default_parameters=ExtractKeyframesParameters().model_dump(mode="json"),
        # Enable reuse once deployment pins and fingerprints the exact FFmpeg build.
        cacheable=False,
        requires_source_file=True,
        fingerprints=(
            ImplementationFingerprint(name="sampling_policy", value="uniform-capped-v1"),
            ImplementationFingerprint(name="ffmpeg_binary", value="deployment-unpinned"),
        ),
        progress_stages=(
            ProgressStage(
                key="preparing",
                label="Preparing frame extraction",
                stall_after_seconds=60,
            ),
            ProgressStage(
                key="extracting",
                label="Extracting frames",
                stall_after_seconds=180,
            ),
        ),
        outputs=(
            OutputSpec(
                name="index",
                kind=ArtifactKind.JSON,
                media_type="application/json",
                schema_id="veridash.keyframes.index",
                schema_version=1,
            ),
            OutputSpec(
                name="frames",
                kind=ArtifactKind.BLOB,
                media_type="image/jpeg",
                schema_id="veridash.keyframe.jpeg",
                schema_version=1,
                collection=True,
                minimum_items=1,
            ),
        ),
    )

    def __init__(self, ffmpeg_fingerprint: str = UNPINNED_FFMPEG_FINGERPRINT) -> None:
        self.manifest = bind_ffmpeg_fingerprint(type(self).manifest, ffmpeg_fingerprint)

    def run(
        self,
        context: RunContext,
        inputs: Mapping[str, Any],
        parameters: BaseModel,
    ) -> ModuleResult:
        parsed = ExtractKeyframesParameters.model_validate(parameters)
        source = _source_input(inputs)
        context.report_progress(
            stage="preparing",
            completed=0,
            total=1,
            message="Reading video duration",
        )
        duration_seconds = _probe_duration(source.path)
        effective_interval = max(
            parsed.interval_seconds,
            duration_seconds / parsed.max_frames,
        )
        context.report_progress(
            stage="preparing",
            completed=1,
            total=1,
            message="Frame sampling plan ready",
        )
        timestamps = _extract_frames(
            context,
            source.path,
            context.output_directory,
            duration_seconds=duration_seconds,
            interval_seconds=effective_interval,
            max_frames=parsed.max_frames,
            jpeg_quality=parsed.jpeg_quality,
        )
        frame_paths = _validated_frame_paths(context.output_directory, len(timestamps))
        items = [
            KeyframeIndexItem(
                output_name=f"frames_{ordinal:06d}",
                ordinal=ordinal,
                timestamp_seconds=round(max(0.0, timestamp), 6),
            )
            for ordinal, timestamp in enumerate(timestamps, start=1)
        ]
        outputs: dict[str, JsonArtifactOutput | BlobArtifactOutput] = {
            "index": JsonArtifactOutput(
                value=KeyframeIndex(
                    source_sha256=source.sha256,
                    requested_interval_seconds=parsed.interval_seconds,
                    effective_interval_seconds=effective_interval,
                    frames=items,
                ).model_dump(mode="json")
            )
        }
        outputs.update(
            {
                item.output_name: BlobArtifactOutput(path=path)
                for item, path in zip(items, frame_paths, strict=True)
            }
        )
        return ModuleResult(outputs=outputs)


def _source_input(inputs: Mapping[str, Any]) -> FileInput:
    try:
        return FileInput.model_validate(inputs["source_video"])
    except (KeyError, ValueError) as exception:
        raise AnalysisExecutionError(
            kind=ErrorKind.INVALID_INPUT,
            public_message="The source video is unavailable for frame extraction.",
            retryable=False,
            diagnostic=str(exception),
        ) from exception


def _probe_duration(source_path: Path) -> float:
    try:
        completed = subprocess.run(
            (
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,crypto,data",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(source_path),
            ),
            check=False,
            capture_output=True,
            timeout=60,
        )
    except FileNotFoundError as exception:
        raise AnalysisExecutionError(
            kind=ErrorKind.INTERNAL_BUG,
            public_message="The frame extraction tools are not installed.",
            retryable=False,
            diagnostic=str(exception),
        ) from exception
    except subprocess.TimeoutExpired as exception:
        raise AnalysisExecutionError(
            kind=ErrorKind.STALLED,
            public_message="Preparing frame extraction took too long.",
            retryable=True,
            diagnostic=str(exception),
        ) from exception
    if completed.returncode != 0 or len(completed.stdout) > MAX_DURATION_OUTPUT_BYTES:
        raise AnalysisExecutionError(
            kind=ErrorKind.INVALID_INPUT,
            public_message="The video duration could not be read for frame extraction.",
            retryable=False,
            diagnostic=completed.stderr.decode(errors="replace")[-10_000:],
        )
    try:
        value = json.loads(completed.stdout)["format"]["duration"]
        duration = float(value)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exception:
        raise AnalysisExecutionError(
            kind=ErrorKind.INVALID_INPUT,
            public_message="The video has no usable duration for frame extraction.",
            retryable=False,
            diagnostic=str(exception),
        ) from exception
    if not math.isfinite(duration) or duration <= 0:
        raise AnalysisExecutionError(
            kind=ErrorKind.INVALID_INPUT,
            public_message="The video has no usable duration for frame extraction.",
            retryable=False,
            diagnostic=f"invalid duration: {duration!r}",
        )
    return duration


def _extract_frames(
    context: RunContext,
    source_path: Path,
    output_directory: Path,
    *,
    duration_seconds: float,
    interval_seconds: float,
    max_frames: int,
    jpeg_quality: int,
) -> list[float]:
    total_milliseconds = max(1, math.ceil(duration_seconds * 1000))
    context.report_progress(
        stage="extracting",
        completed=0,
        total=total_milliseconds,
        message="Extracting review frames",
    )
    output_pattern = output_directory / "frame_%06d.jpg"
    command = (
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "info",
        "-protocol_whitelist",
        "file,crypto,data",
        "-i",
        str(source_path),
        "-map",
        "0:v:0",
        "-vf",
        (
            "select='isnan(prev_selected_t)+"
            f"gte(t-prev_selected_t\\,{interval_seconds:.12g})',showinfo"
        ),
        "-frames:v",
        str(max_frames),
        "-q:v",
        str(jpeg_quality),
        "-vsync",
        "vfr",
        "-start_number",
        "1",
        "-progress",
        "pipe:1",
        "-nostats",
        "-y",
        str(output_pattern),
    )
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exception:
        raise AnalysisExecutionError(
            kind=ErrorKind.INTERNAL_BUG,
            public_message="The frame extraction tools are not installed.",
            retryable=False,
            diagnostic=str(exception),
        ) from exception
    if process.stdout is None:
        process.kill()
        raise RuntimeError("FFmpeg output pipe was not created")
    timestamps: list[float] = []
    diagnostics: list[str] = []
    diagnostic_characters = 0
    for line in process.stdout:
        diagnostics.append(line)
        diagnostic_characters += len(line)
        if diagnostic_characters > 10_000:
            diagnostics = diagnostics[-20:]
            diagnostic_characters = sum(map(len, diagnostics))
        timestamp_match = SHOWINFO_TIMESTAMP.search(line)
        if timestamp_match is not None:
            try:
                timestamps.append(float(timestamp_match.group(1)))
            except ValueError:
                pass
        progress_match = PROGRESS_TIME_US.fullmatch(line.strip())
        if progress_match is not None:
            completed = min(
                total_milliseconds,
                int(progress_match.group(1)) // 1000,
            )
            context.report_progress(
                stage="extracting",
                completed=completed,
                total=total_milliseconds,
                message=f"Extracted {len(timestamps)} frames",
            )
    return_code = process.wait()
    if return_code != 0:
        raise AnalysisExecutionError(
            kind=ErrorKind.INVALID_INPUT,
            public_message="Frames could not be extracted from this video.",
            retryable=False,
            diagnostic="".join(diagnostics)[-10_000:],
        )
    context.report_progress(
        stage="extracting",
        completed=total_milliseconds,
        total=total_milliseconds,
        message=f"Extracted {len(timestamps)} frames",
    )
    return timestamps


def _validated_frame_paths(output_directory: Path, expected_count: int) -> list[Path]:
    paths = sorted(
        path
        for path in output_directory.iterdir()
        if FRAME_FILENAME.fullmatch(path.name) is not None
    )
    if expected_count == 0 or len(paths) != expected_count:
        raise AnalysisExecutionError(
            kind=ErrorKind.INTERNAL_BUG,
            public_message="Frame extraction produced an inconsistent result.",
            retryable=False,
            diagnostic=f"timestamps={expected_count}, files={len(paths)}",
        )
    total_bytes = 0
    for path in paths:
        size_bytes = path.stat().st_size
        total_bytes += size_bytes
        starts_as_jpeg = False
        ends_as_jpeg = False
        if size_bytes >= 4:
            with path.open("rb") as frame:
                starts_as_jpeg = frame.read(2) == b"\xff\xd8"
                frame.seek(-2, 2)
                ends_as_jpeg = frame.read(2) == b"\xff\xd9"
        if size_bytes > MAX_FRAME_BYTES or not starts_as_jpeg or not ends_as_jpeg:
            raise AnalysisExecutionError(
                kind=ErrorKind.INTERNAL_BUG,
                public_message="Frame extraction produced an invalid image.",
                retryable=False,
                diagnostic=f"invalid JPEG output: {path.name}",
            )
    if total_bytes > MAX_TOTAL_FRAME_BYTES:
        raise AnalysisExecutionError(
            kind=ErrorKind.RESOURCE_EXHAUSTED,
            public_message="The extracted frames exceed the configured storage limit.",
            retryable=False,
            diagnostic=f"frame bytes: {total_bytes}",
        )
    return paths
