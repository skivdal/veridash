"""Helpers for binding analysis identity to external executable builds."""

import re

from veridash_analysis.contracts import ImplementationFingerprint, ModuleManifest

UNPINNED_FFMPEG_FINGERPRINT = "deployment-unpinned"
FFMPEG_FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def bind_ffmpeg_fingerprint(
    manifest: ModuleManifest,
    fingerprint: str,
) -> ModuleManifest:
    """Return a cache-safe manifest for one exact FFmpeg/FFprobe build."""
    if fingerprint == UNPINNED_FFMPEG_FINGERPRINT:
        return manifest
    if FFMPEG_FINGERPRINT_PATTERN.fullmatch(fingerprint) is None:
        raise ValueError("FFmpeg fingerprint must be deployment-unpinned or an exact SHA-256")

    fingerprints = tuple(
        ImplementationFingerprint(name=item.name, value=fingerprint)
        if item.name in {"ffmpeg_binary", "ffprobe_binary"}
        else item
        for item in manifest.fingerprints
    )
    digest = fingerprint.removeprefix("sha256:")
    return manifest.model_copy(
        update={
            "version": f"{manifest.version}+ffmpeg.{digest}",
            "cacheable": True,
            "fingerprints": fingerprints,
        }
    )
