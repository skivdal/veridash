"""Explicit registry of lightweight built-in analysis implementations."""

from collections.abc import Callable
from types import MappingProxyType

from veridash_analysis.contracts import AnalysisModule
from veridash_analysis.synthetic import SyntheticAnalysisModule

ModuleFactory = Callable[[], AnalysisModule]

BUILTIN_MODULE_FACTORIES: dict[str, ModuleFactory] = {
    SyntheticAnalysisModule.manifest.module_id: SyntheticAnalysisModule,
}
BUILTIN_MODULES = MappingProxyType(BUILTIN_MODULE_FACTORIES)


def get_builtin_module(module_id: str) -> AnalysisModule:
    try:
        return BUILTIN_MODULES[module_id]()
    except KeyError as exception:
        raise KeyError(f"no worker implementation is registered for {module_id}") from exception
