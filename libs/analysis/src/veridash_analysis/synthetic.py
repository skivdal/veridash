"""Cheap deterministic module used to prove the execution substrate."""

import time
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field
from veridash_core import ArtifactKind, ErrorKind, ResourceClass

from veridash_analysis.contracts import ModuleManifest, OutputSpec, ProgressStage, RunContext
from veridash_analysis.errors import AnalysisExecutionError


class SyntheticParameters(BaseModel):
    steps: int = Field(default=3, ge=1, le=100)
    delay_seconds: float = Field(default=0, ge=0, le=10)
    fail_attempts: int = Field(default=0, ge=0, le=99)


class SyntheticResult(BaseModel):
    steps_completed: int
    deterministic_value: str


class SyntheticAnalysisModule:
    parameter_model: type[BaseModel] = SyntheticParameters
    manifest = ModuleManifest(
        module_id="synthetic_test",
        display_name="Synthetic execution test",
        version="1.0.0",
        result_schema_version=1,
        resource_class=ResourceClass.CPU,
        automatic=False,
        default_parameters=SyntheticParameters().model_dump(mode="json"),
        progress_stages=(
            ProgressStage(key="working", label="Running synthetic steps", stall_after_seconds=30),
        ),
        outputs=(
            OutputSpec(
                name="result",
                kind=ArtifactKind.JSON,
                media_type="application/json",
                schema_id="veridash.synthetic_test",
                schema_version=1,
            ),
        ),
    )

    def run(
        self,
        context: RunContext,
        inputs: Mapping[str, Any],
        parameters: BaseModel,
    ) -> BaseModel:
        del inputs
        parsed = SyntheticParameters.model_validate(parameters)
        if context.attempt_number <= parsed.fail_attempts:
            raise AnalysisExecutionError(
                kind=ErrorKind.TRANSIENT_INFRASTRUCTURE,
                public_message="The synthetic module requested a transient retry.",
                retryable=True,
                diagnostic=f"synthetic failure on attempt {context.attempt_number}",
            )
        for completed in range(1, parsed.steps + 1):
            if context.is_canceled():
                raise AnalysisExecutionError(
                    kind=ErrorKind.CANCELED,
                    public_message="The analysis was canceled.",
                    retryable=False,
                )
            if parsed.delay_seconds:
                time.sleep(parsed.delay_seconds)
            context.report_progress(
                stage="working",
                completed=completed,
                total=parsed.steps,
                message=f"Completed step {completed} of {parsed.steps}",
            )
            context.heartbeat()
        return SyntheticResult(
            steps_completed=parsed.steps,
            deterministic_value=f"synthetic:{parsed.steps}",
        )
