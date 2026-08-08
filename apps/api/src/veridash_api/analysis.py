"""Configured lightweight analysis registry dependency."""

from typing import Annotated, cast

from fastapi import Depends, Request
from veridash_analysis import AnalysisRegistry


def get_analysis_registry(request: Request) -> AnalysisRegistry:
    return cast(AnalysisRegistry, request.app.state.analysis_registry)


ApiAnalysisRegistry = Annotated[AnalysisRegistry, Depends(get_analysis_registry)]
