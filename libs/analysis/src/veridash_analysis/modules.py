"""Explicit registry of lightweight built-in analysis implementations."""

from collections.abc import Callable
from types import MappingProxyType

from veridash_analysis.contracts import AnalysisModule, ModuleManifest
from veridash_analysis.coordinates import ExtractCoordinatesModule
from veridash_analysis.keyframes import ExtractKeyframesModule
from veridash_analysis.probe_media import ProbeMediaModule
from veridash_analysis.stitching import StitchFramesModule
from veridash_analysis.synthetic import SyntheticAnalysisModule
from veridash_analysis.transcription import TranscribeModule

ModuleFactory = Callable[[str], AnalysisModule]


def _extract_keyframes(ffmpeg_fingerprint: str) -> AnalysisModule:
    return ExtractKeyframesModule(ffmpeg_fingerprint)


def _extract_coordinates(_ffmpeg_fingerprint: str) -> AnalysisModule:
    return ExtractCoordinatesModule()


def _probe_media(ffmpeg_fingerprint: str) -> AnalysisModule:
    return ProbeMediaModule(ffmpeg_fingerprint)


def _synthetic(_ffmpeg_fingerprint: str) -> AnalysisModule:
    return SyntheticAnalysisModule()


def _stitch_frames(_ffmpeg_fingerprint: str) -> AnalysisModule:
    return StitchFramesModule()


def _transcribe(_ffmpeg_fingerprint: str) -> AnalysisModule:
    return TranscribeModule()


BUILTIN_MODULE_FACTORIES: dict[str, ModuleFactory] = {
    ExtractCoordinatesModule.manifest.module_id: _extract_coordinates,
    ExtractKeyframesModule.manifest.module_id: _extract_keyframes,
    ProbeMediaModule.manifest.module_id: _probe_media,
    StitchFramesModule.manifest.module_id: _stitch_frames,
    SyntheticAnalysisModule.manifest.module_id: _synthetic,
    TranscribeModule.manifest.module_id: _transcribe,
}
BUILTIN_MODULES = MappingProxyType(BUILTIN_MODULE_FACTORIES)


def get_builtin_module(
    module_id: str,
    *,
    ffmpeg_fingerprint: str = "deployment-unpinned",
) -> AnalysisModule:
    try:
        factory = BUILTIN_MODULES[module_id]
    except KeyError as exception:
        raise KeyError(f"no worker implementation is registered for {module_id}") from exception
    return factory(ffmpeg_fingerprint)


def production_manifests(
    *, ffmpeg_fingerprint: str = "deployment-unpinned"
) -> tuple[ModuleManifest, ...]:
    """Return every production module, including explicit non-automatic tools."""
    modules = tuple(
        get_builtin_module(module_id, ffmpeg_fingerprint=ffmpeg_fingerprint)
        for module_id in BUILTIN_MODULES
    )
    return tuple(
        module.manifest
        for module in modules
        if module.manifest.module_id != SyntheticAnalysisModule.manifest.module_id
    )
