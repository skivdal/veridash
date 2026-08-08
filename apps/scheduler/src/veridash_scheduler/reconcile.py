"""Idempotent PostgreSQL-backed dependency and liveness reconciliation."""

from collections import defaultdict
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from pydantic import JsonValue, TypeAdapter
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from veridash_analysis import ModuleManifest, analysis_cache_key

from veridash_scheduler.config import Settings
from veridash_scheduler.db.sqlc.analysis import AsyncQuerier, ListDependentCacheInputsRow

JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


@dataclass(frozen=True, slots=True)
class ReconcileCounts:
    recovered_attempts: int = 0
    released_retries: int = 0
    blocked_jobs: int = 0
    resolved_jobs: int = 0
    reused_jobs: int = 0


async def reconcile_once(engine: AsyncEngine, settings: Settings) -> ReconcileCounts:
    """Run one finite reconciliation transaction and return transition counts."""
    async with engine.begin() as connection:
        return await reconcile_connection(connection, settings)


async def reconcile_connection(
    connection: AsyncConnection,
    settings: Settings,
) -> ReconcileCounts:
    queries = AsyncQuerier(connection)
    recovered = [
        row
        async for row in queries.recover_expired_analysis_attempts(
            batch_size=settings.batch_size,
            retry_delay_seconds=settings.worker_lost_retry_delay_seconds,
        )
    ]
    released = [
        row async for row in queries.release_due_analysis_retries(batch_size=settings.batch_size)
    ]
    blocked = [
        row async for row in queries.block_failed_dependent_jobs(batch_size=settings.batch_size)
    ]

    dependent_rows = [
        row async for row in queries.list_dependent_cache_inputs(batch_size=settings.batch_size)
    ]
    resolved_count = 0
    reused_count = 0
    for rows in _group_cache_inputs(dependent_rows).values():
        cache_key = _dependent_cache_key(rows)
        resolved = await queries.resolve_analysis_job_cache(
            job_id=rows[0].job_id,
            cache_key=cache_key,
        )
        if resolved is not None:
            resolved_count += 1
            reused_count += int(resolved.reused_from_job_id is not None)

    known_cache_jobs = [
        row
        async for row in queries.list_known_cache_resolvable_jobs(batch_size=settings.batch_size)
    ]
    for candidate in known_cache_jobs:
        if candidate.cache_key is None:
            raise RuntimeError("known-cache candidate has no cache identity")
        resolved = await queries.resolve_analysis_job_cache(
            job_id=candidate.id,
            cache_key=candidate.cache_key,
        )
        if resolved is not None:
            resolved_count += 1
            reused_count += int(resolved.reused_from_job_id is not None)

    return ReconcileCounts(
        recovered_attempts=len(recovered),
        released_retries=len(released),
        blocked_jobs=len(blocked),
        resolved_jobs=resolved_count,
        reused_jobs=reused_count,
    )


def _group_cache_inputs(
    rows: list[ListDependentCacheInputsRow],
) -> dict[UUID, list[ListDependentCacheInputsRow]]:
    grouped: dict[UUID, list[ListDependentCacheInputsRow]] = defaultdict(list)
    for row in rows:
        grouped[row.job_id].append(row)
    return grouped


def _dependent_cache_key(rows: list[ListDependentCacheInputsRow]) -> str:
    first = rows[0]
    if first.source_sha256 is None:
        raise RuntimeError("analysis job source has no content identity")
    manifest_value = ModuleManifest.model_validate(first.manifest)
    if (
        manifest_value.module_id != first.module_id
        or manifest_value.version != first.implementation_version
    ):
        raise RuntimeError("analysis definition columns disagree with its manifest")
    parameters = JSON_OBJECT.validate_python(first.parameters)
    outputs: dict[str, dict[str, str]] = defaultdict(dict)
    dependency_manifests: dict[str, ModuleManifest] = {}
    for row in rows:
        if row.job_id != first.job_id:
            raise RuntimeError("cache inputs from different jobs were grouped together")
        existing = outputs[row.dependency_module_id].get(row.output_name)
        if existing is not None and existing != row.artifact_sha256:
            raise RuntimeError("dependency exposes conflicting named artifact hashes")
        outputs[row.dependency_module_id][row.output_name] = row.artifact_sha256
        dependency_manifest = ModuleManifest.model_validate(row.dependency_manifest)
        dependency_manifests[row.dependency_module_id] = dependency_manifest
        expected_outputs = {output.name: output for output in dependency_manifest.outputs}
        expected = expected_outputs.get(row.output_name)
        if expected is None:
            raise RuntimeError("dependency published an undeclared output")
        if (
            expected.kind.value != row.artifact_kind
            or expected.media_type != row.artifact_media_type
            or expected.schema_id != row.artifact_schema_id
            or expected.schema_version != row.artifact_schema_version
        ):
            raise RuntimeError("dependency artifact metadata violates its manifest")
    for dependency, dependency_manifest in dependency_manifests.items():
        if set(outputs[dependency]) != {output.name for output in dependency_manifest.outputs}:
            raise RuntimeError("dependency did not publish every required output")
    return analysis_cache_key(
        manifest_value,
        source_sha256=first.source_sha256,
        parameters=parameters,
        dependency_artifact_hashes=cast(dict[str, dict[str, str]], outputs),
    )
