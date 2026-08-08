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
    AnalysisInput,
    ChildRequest,
    ErrorMessage,
    FileInput,
    HeartbeatMessage,
    JsonArtifactOutput,
    JsonInput,
    ModuleManifest,
    ProgressMessage,
    ResultMessage,
    manifest_document,
    resolve_output_specs,
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
    PublishBlobAnalysisArtifactParams,
    PublishJsonAnalysisArtifactParams,
    ReportAnalysisAttemptProgressParams,
)

JSON_OBJECT = TypeAdapter(dict[str, JsonValue])
CHILD_ENVIRONMENT_KEYS = (
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "LD_LIBRARY_PATH",
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
    attempt_directory = settings.data_root / "staging" / "attempts" / str(claim.id)
    try:
        attempt_directory.mkdir(mode=0o750, parents=True, exist_ok=False)
        input_directory = attempt_directory / "inputs"
        output_directory = attempt_directory / "outputs"
        input_directory.mkdir(mode=0o750)
        output_directory.mkdir(mode=0o750)
        inputs = await _materialize_inputs(engine, claim, settings, input_directory)
        return await _supervise_child(engine, claim, settings, inputs, output_directory)
    except ChildProtocolError as exception:
        return await _fail_internal(engine, claim, str(exception), "", settings)
    finally:
        shutil.rmtree(attempt_directory, ignore_errors=True)


async def _supervise_child(
    engine: AsyncEngine,
    claim: ClaimReadyAnalysisJobRow,
    settings: Settings,
    inputs: dict[str, AnalysisInput],
    output_directory: Path,
) -> AttemptOutcome:
    try:
        request, manifest = _validated_request_and_manifest(
            claim,
            inputs,
            output_directory,
            settings,
        )
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
        env=child_environment(settings),
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
            await _publish_result(engine, claim, manifest, terminal, settings, output_directory)
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
    inputs: dict[str, AnalysisInput],
    output_directory: Path,
    settings: Settings,
) -> tuple[ChildRequest, ModuleManifest]:
    try:
        persisted = ModuleManifest.model_validate(claim.manifest)
        installed = get_builtin_module(
            claim.module_id,
            ffmpeg_fingerprint=settings.ffmpeg_fingerprint,
        ).manifest
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
            ffmpeg_fingerprint=settings.ffmpeg_fingerprint,
            attempt_number=claim.attempt_number,
            output_directory=output_directory,
            parameters=parameters,
            inputs=inputs,
        ),
        installed,
    )


async def _materialize_inputs(
    engine: AsyncEngine,
    claim: ClaimReadyAnalysisJobRow,
    settings: Settings,
    input_directory: Path,
) -> dict[str, AnalysisInput]:
    try:
        module = get_builtin_module(
            claim.module_id,
            ffmpeg_fingerprint=settings.ffmpeg_fingerprint,
        )
    except KeyError as exception:
        raise ChildProtocolError("claimed job does not match an installed module") from exception
    inputs: dict[str, AnalysisInput] = {}
    store = FilesystemBlobStore(settings.data_root)
    if module.manifest.requires_source_file:
        if (
            claim.source_sha256 is None
            or claim.source_blob_key != claim.source_sha256
            or claim.source_size_bytes is None
            or claim.source_media_type is None
        ):
            raise ChildProtocolError("claimed job source has no valid immutable blob identity")
        try:
            path = store.materialize(claim.source_sha256, input_directory / "source-video")
        except (FileNotFoundError, OSError, ValueError) as exception:
            raise ChildProtocolError("source blob could not be materialized") from exception
        inputs["source_video"] = FileInput(
            path=path,
            sha256=claim.source_sha256,
            size_bytes=claim.source_size_bytes,
            media_type=claim.source_media_type,
        )

    async with engine.connect() as connection:
        rows = [
            row
            async for row in AsyncQuerier(connection).list_analysis_dependency_artifacts(
                project_id=claim.project_id,
                job_id=claim.job_id,
            )
        ]
    grouped_names: dict[str, list[str]] = {}
    for row in rows:
        grouped_names.setdefault(row.dependency_module_id, []).append(row.output_name)
    if set(grouped_names) != set(module.manifest.dependencies):
        raise ChildProtocolError("dependency artifacts do not match the installed manifest")

    for dependency_id, output_names in grouped_names.items():
        try:
            dependency_manifest = get_builtin_module(
                dependency_id,
                ffmpeg_fingerprint=settings.ffmpeg_fingerprint,
            ).manifest
            resolved_specs = resolve_output_specs(dependency_manifest, output_names)
        except (KeyError, ValueError) as exception:
            raise ChildProtocolError("dependency output contract is not installed") from exception
        for row in (item for item in rows if item.dependency_module_id == dependency_id):
            spec = resolved_specs[row.output_name]
            artifact_kind = models.AnalysisArtifactKind(row.kind)
            if (
                spec.kind.value != artifact_kind.value
                or spec.media_type != row.media_type
                or spec.schema_id != row.schema_id
                or spec.schema_version != row.schema_version
            ):
                raise ChildProtocolError("dependency artifact metadata violates its manifest")
            input_name = f"{dependency_id}.{row.output_name}"
            if artifact_kind is models.AnalysisArtifactKind.JSON:
                if row.json_payload is None or row.blob_key is not None:
                    raise ChildProtocolError("dependency JSON artifact is malformed")
                inputs[input_name] = JsonInput(
                    sha256=row.sha256_hex,
                    size_bytes=row.size_bytes,
                    media_type=row.media_type,
                    schema_id=row.schema_id,
                    schema_version=row.schema_version,
                    value=cast(JsonValue, cast(object, row.json_payload)),
                )
                continue
            if row.blob_key != row.sha256_hex or row.json_payload is not None:
                raise ChildProtocolError("dependency blob artifact is malformed")
            dependency_directory = input_directory / dependency_id
            dependency_directory.mkdir(mode=0o750, exist_ok=True)
            try:
                path = store.materialize(
                    row.sha256_hex,
                    dependency_directory / row.output_name,
                )
            except (FileNotFoundError, OSError, ValueError) as exception:
                raise ChildProtocolError("dependency blob could not be materialized") from exception
            inputs[input_name] = FileInput(
                path=path,
                sha256=row.sha256_hex,
                size_bytes=row.size_bytes,
                media_type=row.media_type,
                schema_id=row.schema_id,
                schema_version=row.schema_version,
            )
    return inputs


def child_environment(settings: Settings | None = None) -> dict[str, str]:
    """Build an allowlisted child environment with no database credentials."""
    environment = {key: os.environ[key] for key in CHILD_ENVIRONMENT_KEYS if key in os.environ}
    environment["PYTHONUNBUFFERED"] = "1"
    if settings is not None:
        environment["VERIDASH_TRANSCRIPTION_MODEL_PATH"] = str(
            settings.resolved_transcription_model_path
        )
        environment["VERIDASH_TRANSCRIPTION_DEVICE"] = settings.transcription_device
        environment["VERIDASH_TRANSCRIPTION_COMPUTE_TYPE"] = settings.transcription_compute_type
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
    settings: Settings,
    output_directory: Path,
) -> None:
    specs, canonical_json_outputs, blob_outputs = await asyncio.to_thread(
        _prepare_outputs,
        manifest,
        message,
        settings,
        output_directory,
    )

    async with engine.begin() as connection:
        queries = AsyncQuerier(connection)
        for output_name, document, content in canonical_json_outputs:
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
        for output_name, sha256, size_bytes in blob_outputs:
            spec = specs[output_name]
            published = await queries.publish_blob_analysis_artifact(
                PublishBlobAnalysisArtifactParams(
                    attempt_id=claim.id,
                    lease_token=claim.lease_token,
                    artifact_id=uuid4(),
                    sha256_hex=sha256,
                    size_bytes=size_bytes,
                    media_type=spec.media_type,
                    blob_key=sha256,
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


def _prepare_outputs(
    manifest: ModuleManifest,
    message: ResultMessage,
    settings: Settings,
    output_directory: Path,
):
    try:
        specs = resolve_output_specs(manifest, message.outputs)
    except ValueError as exception:
        raise ChildProtocolError(str(exception)) from exception
    canonical_json_outputs: list[tuple[str, str, bytes]] = []
    blob_outputs: list[tuple[str, str, int]] = []
    store = FilesystemBlobStore(settings.data_root)
    resolved_output_directory = output_directory.resolve(strict=True)
    seen_paths: set[Path] = set()
    for output_name, output in message.outputs.items():
        spec = specs[output_name]
        if isinstance(output, JsonArtifactOutput):
            if spec.kind is not ArtifactKind.JSON:
                raise ChildProtocolError("child returned JSON for a blob output")
            document = json.dumps(
                output.value,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            canonical_json_outputs.append((output_name, document, document.encode()))
            continue
        if spec.kind is not ArtifactKind.BLOB:
            raise ChildProtocolError("child returned a blob for a JSON output")
        if output.path.is_symlink():
            raise ChildProtocolError("child output must not be a symbolic link")
        try:
            resolved_path = output.path.resolve(strict=True)
            resolved_path.relative_to(resolved_output_directory)
        except (FileNotFoundError, OSError, ValueError) as exception:
            raise ChildProtocolError(
                "child blob output is outside its output directory"
            ) from exception
        if not resolved_path.is_file():
            raise ChildProtocolError("child blob output is not a regular file")
        if resolved_path in seen_paths:
            raise ChildProtocolError("child returned the same blob path more than once")
        seen_paths.add(resolved_path)
        published = store.publish(resolved_path, media_type=spec.media_type)
        blob_outputs.append((output_name, published.sha256, published.size_bytes))
    return specs, canonical_json_outputs, blob_outputs


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
