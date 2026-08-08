"""Explicit registry of lightweight built-in analysis implementations."""

from collections.abc import Callable
from types import MappingProxyType

from veridash_analysis.contracts import AnalysisModule, ModuleManifest
from veridash_analysis.keyframes import ExtractKeyframesModule
from veridash_analysis.probe_media import ProbeMediaModule
from veridash_analysis.synthetic import SyntheticAnalysisModule

ModuleFactory = Callable[[str], AnalysisModule]


def _extract_keyframes(ffmpeg_fingerprint: str) -> AnalysisModule:
    return ExtractKeyframesModule(ffmpeg_fingerprint)


def _probe_media(ffmpeg_fingerprint: str) -> AnalysisModule:
    return ProbeMediaModule(ffmpeg_fingerprint)


def _synthetic(_ffmpeg_fingerprint: str) -> AnalysisModule:
    return SyntheticAnalysisModule()


BUILTIN_MODULE_FACTORIES: dict[str, ModuleFactory] = {
    ExtractKeyframesModule.manifest.module_id: _extract_keyframes,
    ProbeMediaModule.manifest.module_id: _probe_media,
    SyntheticAnalysisModule.manifest.module_id: _synthetic,
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
    """Return scheduler-visible manifests enabled in normal project plans."""
    modules = tuple(
        get_builtin_module(module_id, ffmpeg_fingerprint=ffmpeg_fingerprint)
        for module_id in BUILTIN_MODULES
    )
    return tuple(module.manifest for module in modules if module.manifest.automatic)
