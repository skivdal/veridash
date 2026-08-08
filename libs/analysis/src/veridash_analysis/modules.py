"""Explicit registry of lightweight built-in analysis implementations."""

from collections.abc import Callable
from types import MappingProxyType

from veridash_analysis.contracts import AnalysisModule, ModuleManifest
from veridash_analysis.keyframes import ExtractKeyframesModule
from veridash_analysis.probe_media import ProbeMediaModule
from veridash_analysis.synthetic import SyntheticAnalysisModule

ModuleFactory = Callable[[], AnalysisModule]

BUILTIN_MODULE_FACTORIES: dict[str, ModuleFactory] = {
    ExtractKeyframesModule.manifest.module_id: ExtractKeyframesModule,
    ProbeMediaModule.manifest.module_id: ProbeMediaModule,
    SyntheticAnalysisModule.manifest.module_id: SyntheticAnalysisModule,
}
BUILTIN_MODULES = MappingProxyType(BUILTIN_MODULE_FACTORIES)


def get_builtin_module(module_id: str) -> AnalysisModule:
    try:
        return BUILTIN_MODULES[module_id]()
    except KeyError as exception:
        raise KeyError(f"no worker implementation is registered for {module_id}") from exception


def production_manifests() -> tuple[ModuleManifest, ...]:
    """Return scheduler-visible manifests enabled in normal project plans."""
    modules = tuple(factory() for factory in BUILTIN_MODULES.values())
    return tuple(module.manifest for module in modules if module.manifest.automatic)
