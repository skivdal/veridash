"""Typed contracts for adding VeriDash analysis modules."""

from veridash_analysis.contracts import (
    AnalysisModule,
    ImplementationFingerprint,
    ModuleManifest,
    OutputSpec,
    ProgressStage,
)
from veridash_analysis.errors import AnalysisExecutionError
from veridash_analysis.protocol import (
    CHILD_MESSAGE_ADAPTER,
    PROTOCOL_VERSION,
    ChildMessage,
    ChildRequest,
    ErrorMessage,
    HeartbeatMessage,
    ProgressMessage,
    ResultMessage,
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
    "CHILD_MESSAGE_ADAPTER",
    "PROTOCOL_VERSION",
    "AnalysisExecutionError",
    "AnalysisModule",
    "AnalysisRegistry",
    "ChildMessage",
    "ChildRequest",
    "ErrorMessage",
    "HeartbeatMessage",
    "ImplementationFingerprint",
    "InvalidAnalysisGraphError",
    "ModuleManifest",
    "OutputSpec",
    "ProgressMessage",
    "ProgressStage",
    "ResultMessage",
    "analysis_cache_key",
    "analysis_request_key",
    "manifest_document",
    "manifest_hash",
]
