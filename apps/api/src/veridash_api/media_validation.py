"""Bounded, non-networked validation of staged source media."""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast


class InvalidMediaError(ValueError):
    """The staged bytes are not a supported video."""


class MediaValidationUnavailableError(RuntimeError):
    """The local validation tool could not be executed reliably."""


@dataclass(frozen=True, slots=True)
class ValidatedMedia:
    media_type: str
    format_name: str


def _media_type_for_format(format_name: str) -> str:
    formats = set(format_name.split(","))
    if formats.intersection({"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}):
        return "video/mp4"
    if "webm" in formats:
        return "video/webm"
    if "matroska" in formats:
        return "video/x-matroska"
    if "avi" in formats:
        return "video/x-msvideo"
    if "mpegts" in formats:
        return "video/mp2t"
    if "mpeg" in formats:
        return "video/mpeg"
    if "ogg" in formats:
        return "video/ogg"
    return "application/octet-stream"


async def validate_video(
    path: Path,
    *,
    ffprobe_executable: str,
    timeout_seconds: int,
) -> ValidatedMedia:
    """Require at least one video stream without allowing network protocols."""
    try:
        process = await asyncio.create_subprocess_exec(
            ffprobe_executable,
            "-v",
            "error",
            "-protocol_whitelist",
            "file,crypto,data",
            "-show_entries",
            "stream=codec_type:format=format_name",
            "-of",
            "json",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exception:
        raise MediaValidationUnavailableError("ffprobe could not be started") from exception

    try:
        stdout, _stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout_seconds,
        )
    except TimeoutError as exception:
        process.kill()
        await process.wait()
        raise MediaValidationUnavailableError("ffprobe timed out") from exception

    if process.returncode != 0:
        raise InvalidMediaError("The uploaded file is not a readable video.")

    try:
        payload_value: object = json.loads(stdout)
    except (json.JSONDecodeError, UnicodeDecodeError) as exception:
        raise MediaValidationUnavailableError("ffprobe returned invalid output") from exception
    if not isinstance(payload_value, dict):
        raise MediaValidationUnavailableError("ffprobe returned an invalid document")
    payload = cast(dict[str, object], payload_value)

    streams = payload.get("streams")
    if not isinstance(streams, list):
        raise InvalidMediaError("The uploaded file does not contain a video stream.")
    stream_values = cast(list[object], streams)
    has_video_stream = False
    for stream_value in stream_values:
        if isinstance(stream_value, dict):
            stream = cast(dict[str, object], stream_value)
            if stream.get("codec_type") == "video":
                has_video_stream = True
                break
    if not has_video_stream:
        raise InvalidMediaError("The uploaded file does not contain a video stream.")

    format_value = payload.get("format")
    if not isinstance(format_value, dict):
        raise MediaValidationUnavailableError("ffprobe omitted the container format")
    format_payload = cast(dict[str, object], format_value)
    format_name = format_payload.get("format_name")
    if not isinstance(format_name, str) or not format_name:
        raise MediaValidationUnavailableError("ffprobe omitted the container name")
    return ValidatedMedia(
        media_type=_media_type_for_format(format_name),
        format_name=format_name,
    )
