"""Database-owning supervisor around isolated single-attempt child processes."""

import asyncio
import hashlib
import json
import os
import shutil
import signal
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

from pydantic import JsonValue, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine
from veridash_analysis import (
    CHILD_MESSAGE_ADAPTER,
    ChildRequest,
    ErrorMessage,
    FileInput,
    HeartbeatMessage,
    ModuleManifest,
    ProgressMessage,
    ResultMessage,
    manifest_document,
)
from veridash_analysis.modules import get_builtin_module
from veridash_core import ArtifactKind, ErrorKind, ResourceClass
from veridash_storage import FilesystemBlobStore

from veridash_worker.config import Settings
from veridash_worker.db.sqlc import models
from veridash_worker.db.sqlc.attempts import (
    AsyncQuerier,
    CancelAnalysisAttemptRow,
    ClaimReadyAnalysisJobParams,
    ClaimReadyAnalysisJobRow,
    FailAnalysisAttemptParams,
    PublishJsonAnalysisArtifactParams,
    ReportAnalysisAttemptProgressParams,
)

JSON_OBJECT = TypeAdapter(dict[str, JsonValue])
CHILD_ENVIRONMENT_KEYS = (
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "TEMP",
    "TMP",
    "TMPDIR",
)


class LeaseLostError(RuntimeError):
    """The attempt is no longer owned by this supervisor."""


class AttemptCanceledError(RuntimeError):
    """The server has durably requested cancellation of this attempt."""


class ChildProtocolError(RuntimeError):
    """The child violated its narrow, versioned wire contract."""


@dataclass(frozen=True, slots=True)
class AttemptOutcome:
    job_id: UUID
    state: str


@dataclass(slots=True)
class ProgressTracker:
    stage_order: dict[str, int]
    stage_stall_seconds: dict[str, int]
    startup_stall_seconds: float
    last_advance_at: float
    current_stage: str | None = None
    completed: int | None = None

    @classmethod
    def for_manifest(
        cls, manifest: ModuleManifest, startup_stall_seconds: float
    ) -> "ProgressTracker":
        return cls(
            stage_order={stage.key: index for index, stage in enumerate(manifest.progress_stages)},
            stage_stall_seconds={
                stage.key: stage.stall_after_seconds
                for stage in manifest.progress_stages
                if stage.stall_after_seconds is not None
            },
            startup_stall_seconds=startup_stall_seconds,
            last_advance_at=time.monotonic(),
        )

    def observe(self, message: ProgressMessage) -> None:
        now = time.monotonic()
        if self.current_stage is None:
            self.current_stage = message.stage
            self.completed = message.completed
            self.last_advance_at = now
            return
        current_order = self.stage_order[self.current_stage]
        next_order = self.stage_order[message.stage]
        if next_order < current_order:
            raise ChildProtocolError("child progress moved backward to an earlier stage")
        if next_order > current_order:
            self.current_stage = message.stage
            self.completed = message.completed
            self.last_advance_at = now
            return
        if (
            self.completed is not None
            and message.completed is not None
            and message.completed < self.completed
        ):
            raise ChildProtocolError("child progress moved backward within a stage")
        if message.completed is not None and (
            self.completed is None or message.completed > self.completed
        ):
            self.last_advance_at = now
        self.completed = message.completed

    def remaining_seconds(self) -> float:
        stall_seconds = (
            self.startup_stall_seconds
            if self.current_stage is None
            else self.stage_stall_seconds.get(self.current_stage, self.startup_stall_seconds)
        )
        return stall_seconds - (time.monotonic() - self.last_advance_at)


async def claim_once(
    engine: AsyncEngine,
    *,
    resource_class: ResourceClass,
    worker_id: str,
    settings: Settings,
) -> ClaimReadyAnalysisJobRow | None:
    """Atomically claim the next runnable job in this resource pool."""
    async with engine.begin() as connection:
        return await AsyncQuerier(connection).claim_ready_analysis_job(
            ClaimReadyAnalysisJobParams(
                resource_class=models.AnalysisResourceClass(resource_class.value),
                attempt_id=uuid4(),
                worker_id=worker_id,
                lease_token=uuid4(),
                lease_seconds=settings.lease_seconds,
            )
        )


async def supervise_attempt(
    engine: AsyncEngine,
    claim: ClaimReadyAnalysisJobRow,
    settings: Settings,
) -> AttemptOutcome:
    """Run one child and make its terminal result durable if the lease remains valid."""
    scratch_directory = settings.data_root / "scratch" / "attempts" / str(claim.id)
    try:
        inputs = _materialize_inputs(claim, settings, scratch_directory)
        return await _supervise_child(engine, claim, settings, inputs)
    except ChildProtocolError as exception:
        return await _fail_internal(engine, claim, str(exception), "", settings)
    finally:
        shutil.rmtree(scratch_directory, ignore_errors=True)


async def _supervise_child(
    engine: AsyncEngine,
    claim: ClaimReadyAnalysisJobRow,
    settings: Settings,
    inputs: dict[str, FileInput],
) -> AttemptOutcome:
    try:
        request, manifest = _validated_request_and_manifest(claim, inputs)
    except ChildProtocolError as exception:
        return await _fail_internal(engine, claim, str(exception), "", settings)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "veridash_worker.child",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=settings.max_protocol_line_bytes + 1,
        env=child_environment(),
        start_new_session=True,
    )
    if process.stdin is None or process.stdout is None or process.stderr is None:
        process.kill()
        raise RuntimeError("child process pipes were not created")

    stderr_task = asyncio.create_task(
        _read_capped(process.stderr, settings.max_stderr_bytes),
        name=f"stderr-{claim.id}",
    )
    process.stdin.write(request.model_dump_json().encode() + b"\n")
    await process.stdin.drain()
    process.stdin.close()

    terminal: ResultMessage | ErrorMessage | None = None
    protocol_failure: str | None = None
    stalled_failure: str | None = None
    cancellation_requested = False
    progress_tracker = ProgressTracker.for_manifest(manifest, settings.startup_stall_seconds)
    try:
        while True:
            try:
                line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=max(
                        0.01,
                        min(
                            settings.heartbeat_interval_seconds,
                            progress_tracker.remaining_seconds(),
                        ),
                    ),
                )
            except TimeoutError:
                if progress_tracker.remaining_seconds() <= 0:
                    stalled_failure = "child stopped making semantic progress"
                    break
                await _renew_lease(engine, claim, settings)
                continue
            except ValueError:
                protocol_failure = "child protocol line exceeds the configured limit"
                break
            if not line:
                break
            if len(line) > settings.max_protocol_line_bytes:
                protocol_failure = "child protocol line exceeds the configured limit"
                break
            if terminal is not None:
                protocol_failure = "child emitted data after its terminal message"
                break
            try:
                message = CHILD_MESSAGE_ADAPTER.validate_json(line)
            except (ValidationError, ValueError):
                protocol_failure = "child emitted an invalid protocol message"
                break
            if isinstance(message, HeartbeatMessage):
                await _renew_lease(engine, claim, settings)
            elif isinstance(message, ProgressMessage):
                _validate_progress(message, manifest)
                progress_tracker.observe(message)
                await _report_progress(engine, claim, message, settings)
            else:
                terminal = message
                break
            if progress_tracker.remaining_seconds() <= 0:
                stalled_failure = "child stopped making semantic progress"
                break
    except AttemptCanceledError:
        cancellation_requested = True
    except (ChildProtocolError, LeaseLostError) as exception:
        protocol_failure = str(exception)
    except asyncio.CancelledError:
        await _stop_process(process)
        await stderr_task
        raise

    stdout_remainder_task = (
        asyncio.create_task(
            _read_capped(process.stdout, settings.max_protocol_line_bytes),
            name=f"stdout-remainder-{claim.id}",
        )
        if terminal is not None
        else None
    )
    if (
        protocol_failure is not None or stalled_failure is not None or cancellation_requested
    ) and process.returncode is None:
        await _stop_process(process)
    if process.returncode is None:
        try:
            return_code = await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            protocol_failure = "child did not exit after its terminal protocol message"
            await _stop_process(process)
            return_code = await process.wait()
    else:
        return_code = process.returncode
    if stdout_remainder_task is not None and (await stdout_remainder_task).strip():
        protocol_failure = "child emitted data after its terminal message"
    stderr = (await stderr_task).decode(errors="replace")

    if cancellation_requested:
        canceled = await _record_requested_cancellation(engine, claim)
        if canceled is None:
            raise LeaseLostError("attempt lease was lost while recording cancellation")
        return _canceled_outcome(claim, canceled)
    if stalled_failure is not None:
        return await _fail(
            engine,
            claim,
            error_kind=ErrorKind.STALLED,
            public_message="The analysis stopped because it stopped making progress.",
            retryable=True,
            diagnostic=_diagnostic_document(stalled_failure, stderr),
            settings=settings,
        )
    if protocol_failure is not None:
        return await _fail_internal(engine, claim, protocol_failure, stderr, settings)
    if terminal is None:
        return await _fail_internal(
            engine,
            claim,
            f"child exited with status {return_code} without a terminal message",
            stderr,
            settings,
        )
    if isinstance(terminal, ResultMessage):
        if return_code != 0:
            return await _fail_internal(
                engine,
                claim,
                f"child returned a result but exited with status {return_code}",
                stderr,
                settings,
            )
        try:
            await _renew_lease(engine, claim, settings)
            await _publish_result(engine, claim, manifest, terminal)
        except AttemptCanceledError as exception:
            canceled = await _record_requested_cancellation(engine, claim)
            if canceled is None:
                raise LeaseLostError(
                    "attempt lease was lost while recording cancellation"
                ) from exception
            return _canceled_outcome(claim, canceled)
        except LeaseLostError:
            canceled = await _record_requested_cancellation(engine, claim)
            if canceled is not None:
                return _canceled_outcome(claim, canceled)
            raise
        except ChildProtocolError as exception:
            return await _fail_internal(engine, claim, str(exception), stderr, settings)
        return AttemptOutcome(job_id=claim.job_id, state="succeeded")
    if return_code == 0:
        return await _fail_internal(
            engine,
            claim,
            "child returned an error but exited successfully",
            stderr,
            settings,
        )
    return await _record_child_error(engine, claim, terminal, stderr, settings)


def _validated_request_and_manifest(
    claim: ClaimReadyAnalysisJobRow,
    inputs: dict[str, FileInput],
) -> tuple[ChildRequest, ModuleManifest]:
    try:
        persisted = ModuleManifest.model_validate(claim.manifest)
        installed = get_builtin_module(claim.module_id).manifest
        parameters = JSON_OBJECT.validate_python(claim.parameters)
    except (KeyError, ValidationError, ValueError) as exception:
        raise ChildProtocolError("claimed job does not match an installed module") from exception
    if manifest_document(persisted) != manifest_document(installed):
        raise ChildProtocolError("persisted and installed module manifests differ")
    if installed.version != claim.implementation_version:
        raise ChildProtocolError("claimed implementation version is not installed")
    return (
        ChildRequest(
            module_id=claim.module_id,
            implementation_version=claim.implementation_version,
            attempt_number=claim.attempt_number,
            parameters=parameters,
            inputs=inputs,
        ),
        installed,
    )


def _materialize_inputs(
    claim: ClaimReadyAnalysisJobRow,
    settings: Settings,
    scratch_directory: Path,
) -> dict[str, FileInput]:
    try:
        module = get_builtin_module(claim.module_id)
    except KeyError as exception:
        raise ChildProtocolError("claimed job does not match an installed module") from exception
    if not module.manifest.requires_source_file:
        return {}
    if (
        claim.source_sha256 is None
        or claim.source_blob_key != claim.source_sha256
        or claim.source_size_bytes is None
        or claim.source_media_type is None
    ):
        raise ChildProtocolError("claimed job source has no valid immutable blob identity")
    scratch_directory.mkdir(mode=0o750, parents=True, exist_ok=False)
    try:
        path = FilesystemBlobStore(settings.data_root).materialize(
            claim.source_sha256,
            scratch_directory / "source-video",
        )
    except (FileNotFoundError, OSError, ValueError) as exception:
        raise ChildProtocolError("source blob could not be materialized") from exception
    return {
        "source_video": FileInput(
            path=path,
            sha256=claim.source_sha256,
            size_bytes=claim.source_size_bytes,
            media_type=claim.source_media_type,
        )
    }


def child_environment() -> dict[str, str]:
    """Build an allowlisted child environment with no database credentials."""
    environment = {key: os.environ[key] for key in CHILD_ENVIRONMENT_KEYS if key in os.environ}
    environment["PYTHONUNBUFFERED"] = "1"
    return environment


def _validate_progress(message: ProgressMessage, manifest: ModuleManifest) -> None:
    if message.stage not in {stage.key for stage in manifest.progress_stages}:
        raise ChildProtocolError("child reported an undeclared progress stage")
    if message.completed is not None and message.total is None:
        raise ChildProtocolError("child reported completed progress without a total")
    if (
        message.completed is not None
        and message.total is not None
        and message.completed > message.total
    ):
        raise ChildProtocolError("child progress exceeds its total")


async def _renew_lease(
    engine: AsyncEngine,
    claim: ClaimReadyAnalysisJobRow,
    settings: Settings,
) -> None:
    async with engine.begin() as connection:
        renewed = await AsyncQuerier(connection).renew_analysis_attempt_lease(
            lease_seconds=settings.lease_seconds,
            attempt_id=claim.id,
            lease_token=claim.lease_token,
        )
    if renewed is None:
        raise LeaseLostError("attempt lease was lost")
    if renewed.cancel_requested_at is not None:
        raise AttemptCanceledError


async def _report_progress(
    engine: AsyncEngine,
    claim: ClaimReadyAnalysisJobRow,
    message: ProgressMessage,
    settings: Settings,
) -> None:
    async with engine.begin() as connection:
        updated = await AsyncQuerier(connection).report_analysis_attempt_progress(
            ReportAnalysisAttemptProgressParams(
                lease_seconds=settings.lease_seconds,
                progress_stage=message.stage,
                progress_completed=message.completed,
                progress_total=message.total,
                progress_message=message.message,
                attempt_id=claim.id,
                lease_token=claim.lease_token,
            )
        )
    if updated is None:
        raise LeaseLostError("attempt lease was lost while reporting progress")
    if updated.cancel_requested_at is not None:
        raise AttemptCanceledError


async def _publish_result(
    engine: AsyncEngine,
    claim: ClaimReadyAnalysisJobRow,
    manifest: ModuleManifest,
    message: ResultMessage,
) -> None:
    specs = {output.name: output for output in manifest.outputs}
    if set(message.outputs) != set(specs):
        raise ChildProtocolError("child result does not contain every declared output")
    canonical_outputs: list[tuple[str, str, bytes]] = []
    for output_name, value in message.outputs.items():
        spec = specs[output_name]
        if spec.kind is not ArtifactKind.JSON:
            raise ChildProtocolError("blob output publication is not implemented")
        document = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        canonical_outputs.append((output_name, document, document.encode()))

    async with engine.begin() as connection:
        queries = AsyncQuerier(connection)
        for output_name, document, content in canonical_outputs:
            spec = specs[output_name]
            published = await queries.publish_json_analysis_artifact(
                PublishJsonAnalysisArtifactParams(
                    attempt_id=claim.id,
                    lease_token=claim.lease_token,
                    artifact_id=uuid4(),
                    sha256_hex=hashlib.sha256(content).hexdigest(),
                    size_bytes=len(content),
                    media_type=spec.media_type,
                    json_payload=document,
                    schema_id=spec.schema_id,
                    schema_version=spec.schema_version,
                    output_name=output_name,
                )
            )
            if published is None:
                raise LeaseLostError("attempt lease was lost while publishing output")
        completed = await queries.complete_analysis_attempt(
            attempt_id=claim.id,
            lease_token=claim.lease_token,
        )
        if completed is None:
            raise LeaseLostError("attempt lease was lost while completing")


async def _record_child_error(
    engine: AsyncEngine,
    claim: ClaimReadyAnalysisJobRow,
    message: ErrorMessage,
    stderr: str,
    settings: Settings,
) -> AttemptOutcome:
    diagnostic = _diagnostic_document(message.diagnostic, stderr)
    return await _fail(
        engine,
        claim,
        error_kind=message.error_kind,
        public_message=message.public_message,
        retryable=message.retryable,
        diagnostic=diagnostic,
        settings=settings,
    )


async def _fail_internal(
    engine: AsyncEngine,
    claim: ClaimReadyAnalysisJobRow,
    reason: str,
    stderr: str,
    settings: Settings,
) -> AttemptOutcome:
    return await _fail(
        engine,
        claim,
        error_kind=ErrorKind.INTERNAL_BUG,
        public_message="The analysis stopped because of an internal error.",
        retryable=False,
        diagnostic=_diagnostic_document(reason, stderr),
        settings=settings,
    )


async def _fail(
    engine: AsyncEngine,
    claim: ClaimReadyAnalysisJobRow,
    *,
    error_kind: ErrorKind,
    public_message: str,
    retryable: bool,
    diagnostic: Mapping[str, str] | None,
    settings: Settings,
) -> AttemptOutcome:
    diagnostic_id = uuid4() if diagnostic is not None else None
    async with engine.begin() as connection:
        failed = await AsyncQuerier(connection).fail_analysis_attempt(
            FailAnalysisAttemptParams(
                attempt_id=claim.id,
                lease_token=claim.lease_token,
                error_kind=models.AnalysisErrorKind(error_kind.value),
                public_error_message=public_message,
                diagnostic_id=diagnostic_id,
                diagnostic_details=json.dumps(diagnostic) if diagnostic is not None else None,
                retry_delay_seconds=settings.retry_delay_seconds if retryable else None,
            )
        )
    if failed is None:
        canceled = await _record_requested_cancellation(engine, claim)
        if canceled is not None:
            return _canceled_outcome(claim, canceled)
        raise LeaseLostError("attempt lease was lost while recording failure")
    return AttemptOutcome(job_id=claim.job_id, state=cast(str, failed.state))


async def _record_requested_cancellation(
    engine: AsyncEngine,
    claim: ClaimReadyAnalysisJobRow,
) -> CancelAnalysisAttemptRow | None:
    async with engine.begin() as connection:
        return await AsyncQuerier(connection).cancel_analysis_attempt(
            attempt_id=claim.id,
            lease_token=claim.lease_token,
        )


def _canceled_outcome(
    claim: ClaimReadyAnalysisJobRow,
    canceled: CancelAnalysisAttemptRow,
) -> AttemptOutcome:
    return AttemptOutcome(job_id=claim.job_id, state=cast(str, canceled.state))


def _diagnostic_document(message: str | None, stderr: str) -> Mapping[str, str] | None:
    values: dict[str, str] = {}
    if message:
        values["message"] = message
    if stderr:
        values["stderr"] = stderr
    return values or None


async def _read_capped(reader: asyncio.StreamReader, limit: int) -> bytes:
    chunks: list[bytes] = []
    remaining = limit
    while True:
        chunk = await reader.read(64 * 1024)
        if not chunk:
            return b"".join(chunks)
        if remaining > 0:
            kept = chunk[:remaining]
            chunks.append(kept)
            remaining -= len(kept)


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except TimeoutError:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()
