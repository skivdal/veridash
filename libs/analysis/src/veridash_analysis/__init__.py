"""Typed contracts for adding VeriDash analysis modules."""

from veridash_analysis.contracts import (
    AnalysisModule,
    ImplementationFingerprint,
    ModuleManifest,
    OutputSpec,
    ProgressStage,
)
from veridash_analysis.registry import (
    AnalysisRegistry,
    InvalidAnalysisGraphError,
    analysis_cache_key,
    analysis_request_key,
    manifest_document,
    manifest_hash,
)

__all__ = [
    "AnalysisModule",
    "AnalysisRegistry",
    "ImplementationFingerprint",
    "InvalidAnalysisGraphError",
    "ModuleManifest",
    "OutputSpec",
    "ProgressStage",
    "analysis_cache_key",
    "analysis_request_key",
    "manifest_document",
    "manifest_hash",
]
