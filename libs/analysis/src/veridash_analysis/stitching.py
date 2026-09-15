"""Explicit, deterministic panorama stitching over selected keyframes."""

import importlib
import importlib.metadata
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
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
from veridash_analysis.protocol import FileInput

FRAME_OUTPUT_NAME = re.compile(r"^frames_[0-9]{6}$")
OPENCV_PACKAGE_VERSION = "4.12.0.88"
MAX_SELECTED_FRAMES = 12
MAX_PANORAMA_PIXELS = 120_000_000
MAX_PANORAMA_BYTES = 100 * 1024 * 1024


class StitchFramesParameters(BaseModel):
    """The ordered keyframe selection is the complete user-controlled input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selected_output_names: list[str] = Field(min_length=2, max_length=MAX_SELECTED_FRAMES)

    @field_validator("selected_output_names")
    @classmethod
    def validate_selection(cls, names: list[str]) -> list[str]:
        if len(names) != len(set(names)):
            raise ValueError("selected frames must be unique")
        if any(FRAME_OUTPUT_NAME.fullmatch(name) is None for name in names):
            raise ValueError("selected frame names have an invalid shape")
        return names


class StitchSourceFrame(BaseModel):
    output_name: str
    sha256: str


class StitchResult(BaseModel):
    algorithm: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    source_frames: list[StitchSourceFrame]


class StitchFramesModule:
    parameter_model: type[BaseModel] = StitchFramesParameters
    manifest = ModuleManifest(
        module_id="stitch_frames",
        display_name="Frame stitching",
        version="1.0.0",
        result_schema_version=1,
        resource_class=ResourceClass.CPU,
        dependencies=("extract_keyframes",),
        automatic=False,
        default_parameters={},
        max_attempts=1,
        cacheable=True,
        fingerprints=(
            ImplementationFingerprint(
                name="opencv_python_headless",
                value=OPENCV_PACKAGE_VERSION,
            ),
            ImplementationFingerprint(
                name="stitch_policy",
                value="panorama-confidence-0.3-single-thread-seeded-jpeg-v1",
            ),
        ),
        progress_stages=(
            ProgressStage(
                key="preparing",
                label="Preparing selected frames",
                stall_after_seconds=60,
            ),
            ProgressStage(
                key="aligning",
                label="Aligning selected frames",
                stall_after_seconds=300,
            ),
            ProgressStage(
                key="encoding",
                label="Encoding panorama",
                stall_after_seconds=60,
            ),
        ),
        outputs=(
            OutputSpec(
                name="result",
                kind=ArtifactKind.JSON,
                media_type="application/json",
                schema_id="veridash.stitch_frames.result",
                schema_version=1,
            ),
            OutputSpec(
                name="panorama",
                kind=ArtifactKind.BLOB,
                media_type="image/jpeg",
                schema_id="veridash.stitch_frames.panorama",
                schema_version=1,
            ),
        ),
    )

    def run(
        self,
        context: RunContext,
        inputs: Mapping[str, Any],
        parameters: BaseModel,
    ) -> ModuleResult:
        parsed = StitchFramesParameters.model_validate(parameters)
        selected = _selected_inputs(inputs, parsed.selected_output_names)
        total = len(selected)
        context.report_progress(
            stage="preparing",
            completed=0,
            total=total,
            message="Reading selected frames",
        )
        for completed, (_, frame) in enumerate(selected, start=1):
            _validate_jpeg_input(frame)
            context.report_progress(
                stage="preparing",
                completed=completed,
                total=total,
                message=f"Prepared {completed} of {total} frames",
            )
        output_path = context.output_directory / "panorama.jpg"
        context.report_progress(
            stage="aligning",
            completed=0,
            total=1,
            message="Finding overlap between selected frames",
        )
        width, height = _stitch([frame.path for _, frame in selected], output_path)
        context.report_progress(
            stage="aligning",
            completed=1,
            total=1,
            message="Frames aligned",
        )
        context.report_progress(
            stage="encoding",
            completed=0,
            total=1,
            message="Validating panorama",
        )
        _validate_panorama(output_path)
        context.report_progress(
            stage="encoding",
            completed=1,
            total=1,
            message="Panorama ready",
        )
        result = StitchResult(
            algorithm="opencv_panorama",
            width=width,
            height=height,
            source_frames=[
                StitchSourceFrame(output_name=name, sha256=frame.sha256) for name, frame in selected
            ],
        )
        return ModuleResult(
            outputs={
                "result": JsonArtifactOutput(value=result.model_dump(mode="json")),
                "panorama": BlobArtifactOutput(path=output_path),
            }
        )


def _selected_inputs(
    inputs: Mapping[str, Any],
    selected_output_names: list[str],
) -> list[tuple[str, FileInput]]:
    selected: list[tuple[str, FileInput]] = []
    for output_name in selected_output_names:
        input_name = f"extract_keyframes.{output_name}"
        try:
            frame = FileInput.model_validate(inputs[input_name])
        except (KeyError, ValueError) as exception:
            raise AnalysisExecutionError(
                kind=ErrorKind.INVALID_INPUT,
                public_message="A selected frame is no longer available for stitching.",
                retryable=False,
                diagnostic=f"missing or invalid input: {input_name}",
            ) from exception
        if (
            frame.media_type != "image/jpeg"
            or frame.schema_id != "veridash.keyframe.jpeg"
            or frame.schema_version != 1
        ):
            raise AnalysisExecutionError(
                kind=ErrorKind.INVALID_INPUT,
                public_message="A selected frame has an unsupported format.",
                retryable=False,
                diagnostic=f"unexpected frame contract: {input_name}",
            )
        selected.append((output_name, frame))
    return selected


def _validate_jpeg_input(frame: FileInput) -> None:
    try:
        size = frame.path.stat().st_size
        with frame.path.open("rb") as content:
            starts_as_jpeg = content.read(2) == b"\xff\xd8"
            content.seek(-2, 2)
            ends_as_jpeg = content.read(2) == b"\xff\xd9"
    except (OSError, ValueError) as exception:
        raise AnalysisExecutionError(
            kind=ErrorKind.INVALID_INPUT,
            public_message="A selected frame could not be read.",
            retryable=False,
            diagnostic=str(exception),
        ) from exception
    if size != frame.size_bytes or size < 4 or not starts_as_jpeg or not ends_as_jpeg:
        raise AnalysisExecutionError(
            kind=ErrorKind.INVALID_INPUT,
            public_message="A selected frame is not a valid JPEG image.",
            retryable=False,
            diagnostic=f"invalid JPEG input: {frame.path.name}",
        )


def _stitch(paths: list[Path], output_path: Path) -> tuple[int, int]:
    try:
        cv2: Any = importlib.import_module("cv2")
        package_version = importlib.metadata.version("opencv-python-headless")
    except ImportError as exception:
        raise AnalysisExecutionError(
            kind=ErrorKind.INTERNAL_BUG,
            public_message="The frame stitching tools are not installed.",
            retryable=False,
            diagnostic=str(exception),
        ) from exception
    # The wheel's build suffix is absent from cv2.__version__ (4.12.0).
    # Compare distribution versions to enforce the declared cache fingerprint.
    if package_version != OPENCV_PACKAGE_VERSION:
        raise AnalysisExecutionError(
            kind=ErrorKind.INTERNAL_BUG,
            public_message=(
                "The server's OpenCV installation does not match the required stitching version."
            ),
            retryable=False,
            diagnostic=(
                f"expected opencv-python-headless {OPENCV_PACKAGE_VERSION}, "
                f"found {package_version} (cv2 {cv2.__version__})"
            ),
        )
    cv2.setNumThreads(1)
    cv2.setRNGSeed(0)
    images: list[Any] = []
    for path in paths:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise AnalysisExecutionError(
                kind=ErrorKind.INVALID_INPUT,
                public_message="A selected frame could not be decoded.",
                retryable=False,
                diagnostic=f"OpenCV could not decode {path.name}",
            )
        images.append(image)
    try:
        stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
        stitcher.setPanoConfidenceThresh(0.3)
        status, panorama = stitcher.stitch(images)
    except Exception as exception:
        raise AnalysisExecutionError(
            kind=ErrorKind.INVALID_INPUT,
            public_message=(
                "The selected frames could not be stitched. Choose frames with visible overlap."
            ),
            retryable=False,
            diagnostic=repr(exception),
        ) from exception
    if status != cv2.Stitcher_OK or panorama is None:
        raise AnalysisExecutionError(
            kind=ErrorKind.INVALID_INPUT,
            public_message=(
                "The selected frames could not be stitched. Choose frames with visible overlap."
            ),
            retryable=False,
            diagnostic=f"OpenCV stitch status: {status}",
        )
    height, width = panorama.shape[:2]
    if width <= 0 or height <= 0 or width * height > MAX_PANORAMA_PIXELS:
        raise AnalysisExecutionError(
            kind=ErrorKind.RESOURCE_EXHAUSTED,
            public_message="The stitched panorama exceeds the configured image limit.",
            retryable=False,
            diagnostic=f"panorama dimensions: {width}x{height}",
        )
    if not cv2.imwrite(str(output_path), panorama, [cv2.IMWRITE_JPEG_QUALITY, 95]):
        raise AnalysisExecutionError(
            kind=ErrorKind.INTERNAL_BUG,
            public_message="The stitched panorama could not be encoded.",
            retryable=False,
            diagnostic="OpenCV imwrite returned false",
        )
    return width, height


def _validate_panorama(path: Path) -> None:
    try:
        size = path.stat().st_size
        with path.open("rb") as content:
            starts_as_jpeg = content.read(2) == b"\xff\xd8"
            content.seek(-2, 2)
            ends_as_jpeg = content.read(2) == b"\xff\xd9"
    except (OSError, ValueError) as exception:
        raise AnalysisExecutionError(
            kind=ErrorKind.INTERNAL_BUG,
            public_message="The stitched panorama could not be validated.",
            retryable=False,
            diagnostic=str(exception),
        ) from exception
    if size < 4 or size > MAX_PANORAMA_BYTES or not starts_as_jpeg or not ends_as_jpeg:
        raise AnalysisExecutionError(
            kind=ErrorKind.INTERNAL_BUG,
            public_message="The frame stitcher produced an invalid panorama.",
            retryable=False,
            diagnostic=f"invalid panorama output: {size} bytes",
        )
