"""Conservative extraction of embedded decimal ISO 6709 coordinates."""

import math
import re
from collections.abc import Mapping
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, JsonValue
from veridash_core import ArtifactKind, ErrorKind, ResourceClass

from veridash_analysis.contracts import (
    ImplementationFingerprint,
    JsonArtifactOutput,
    ModuleManifest,
    ModuleResult,
    OutputSpec,
    ProgressStage,
    RunContext,
)
from veridash_analysis.errors import AnalysisExecutionError
from veridash_analysis.probe_media import ProbeMediaResult
from veridash_analysis.protocol import JsonInput

DECIMAL_ISO_6709 = re.compile(
    r"^\s*(?P<latitude>[+-](?:\d{1,2}(?:\.\d+)?|90(?:\.0+)?))"
    r"(?P<longitude>[+-](?:\d{1,3}(?:\.\d+)?|180(?:\.0+)?))"
    r"(?P<altitude>[+-]\d+(?:\.\d+)?)?/?\s*$"
)
LOCATION_TAG_NAMES = {
    "location",
    "com.apple.quicktime.location.iso6709",
}


class ExtractCoordinatesParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CoordinateCandidate(BaseModel):
    scope: str
    tag: str
    raw_value: str
    latitude: float | None = None
    longitude: float | None = None
    altitude_meters: float | None = None


class CoordinatesResult(BaseModel):
    status: Literal["found", "not_found", "invalid", "ambiguous"]
    latitude: float | None = None
    longitude: float | None = None
    altitude_meters: float | None = None
    candidates: list[CoordinateCandidate]


class ExtractCoordinatesModule:
    parameter_model: type[BaseModel] = ExtractCoordinatesParameters
    manifest = ModuleManifest(
        module_id="extract_coordinates",
        display_name="Map",
        version="1.0.0",
        result_schema_version=1,
        resource_class=ResourceClass.CPU,
        dependencies=("probe_media",),
        default_parameters={},
        cacheable=True,
        fingerprints=(
            ImplementationFingerprint(name="coordinate_parser", value="iso6709-decimal-v1"),
        ),
        progress_stages=(
            ProgressStage(
                key="inspecting",
                label="Inspecting embedded location metadata",
                stall_after_seconds=30,
            ),
        ),
        outputs=(
            OutputSpec(
                name="result",
                kind=ArtifactKind.JSON,
                media_type="application/json",
                schema_id="veridash.coordinates.embedded",
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
        ExtractCoordinatesParameters.model_validate(parameters)
        try:
            artifact = JsonInput.model_validate(inputs["probe_media.result"])
            if artifact.schema_id != "veridash.probe_media.raw" or artifact.schema_version != 1:
                raise ValueError("unexpected probe result schema")
            probe_result = ProbeMediaResult.model_validate(artifact.value)
        except (KeyError, ValueError) as exception:
            raise AnalysisExecutionError(
                kind=ErrorKind.INVALID_INPUT,
                public_message="The metadata result is unavailable for location inspection.",
                retryable=False,
                diagnostic=str(exception),
            ) from exception

        context.report_progress(
            stage="inspecting",
            completed=0,
            total=1,
            message="Checking explicit embedded location tags",
        )
        candidates = extract_coordinate_candidates(probe_result.probe)
        result = summarize_candidates(candidates)
        context.report_progress(
            stage="inspecting",
            completed=1,
            total=1,
            message="Embedded location inspection complete",
        )
        return ModuleResult(
            outputs={"result": JsonArtifactOutput(value=result.model_dump(mode="json"))}
        )


def extract_coordinate_candidates(probe: Mapping[str, JsonValue]) -> list[CoordinateCandidate]:
    """Return every explicit supported location tag without inventing a location."""
    scopes: list[tuple[str, object]] = [("format", probe.get("format"))]
    streams = probe.get("streams")
    if isinstance(streams, list):
        scopes.extend(
            (f"stream:{index}", stream)
            for index, stream in enumerate(cast(list[JsonValue], streams))
        )

    candidates: list[CoordinateCandidate] = []
    for scope, container in scopes:
        if not isinstance(container, dict):
            continue
        container_value = cast(dict[str, JsonValue], container)
        tags = container_value.get("tags")
        if not isinstance(tags, dict):
            continue
        for key, value in cast(dict[str, JsonValue], tags).items():
            if key.casefold() not in LOCATION_TAG_NAMES:
                continue
            if not isinstance(value, str):
                continue
            parsed = parse_decimal_iso_6709(value)
            candidates.append(
                CoordinateCandidate(
                    scope=scope,
                    tag=key,
                    raw_value=value,
                    latitude=None if parsed is None else parsed[0],
                    longitude=None if parsed is None else parsed[1],
                    altitude_meters=None if parsed is None else parsed[2],
                )
            )
    return candidates


def parse_decimal_iso_6709(value: str) -> tuple[float, float, float | None] | None:
    """Parse only the unambiguous signed decimal-degree ISO 6709 representation."""
    match = DECIMAL_ISO_6709.fullmatch(value)
    if match is None:
        return None
    latitude = float(match.group("latitude"))
    longitude = float(match.group("longitude"))
    altitude_text = match.group("altitude")
    altitude = None if altitude_text is None else float(altitude_text)
    if not all(math.isfinite(item) for item in (latitude, longitude)):
        return None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None
    return latitude, longitude, altitude


def summarize_candidates(candidates: list[CoordinateCandidate]) -> CoordinatesResult:
    parsed = [item for item in candidates if item.latitude is not None]
    if not candidates:
        return CoordinatesResult(status="not_found", candidates=[])
    if not parsed:
        return CoordinatesResult(status="invalid", candidates=candidates)
    distinct = {(item.latitude, item.longitude, item.altitude_meters) for item in parsed}
    if len(distinct) != 1:
        return CoordinatesResult(status="ambiguous", candidates=candidates)
    latitude, longitude, altitude = distinct.pop()
    return CoordinatesResult(
        status="found",
        latitude=latitude,
        longitude=longitude,
        altitude_meters=altitude,
        candidates=candidates,
    )
