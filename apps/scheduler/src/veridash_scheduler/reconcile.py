"""Idempotent PostgreSQL-backed dependency and liveness reconciliation."""

from collections import defaultdict
from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid4

from pydantic import JsonValue, TypeAdapter
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from veridash_analysis import (
    AnalysisRegistry,
    ModuleManifest,
    analysis_cache_key,
    build_automatic_analysis_plan,
    match_output_spec,
    resolve_output_specs,
)

from veridash_scheduler.config import Settings
from veridash_scheduler.db.sqlc import models
from veridash_scheduler.db.sqlc.analysis import (
    AsyncQuerier,
    CreateAnalysisJobParams,
    ListDependentCacheInputsRow,
    RegisterAnalysisDefinitionParams,
)

JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


@dataclass(frozen=True, slots=True)
class ReconcileCounts:
    planned_jobs: int = 0
    recovered_attempts: int = 0
    released_retries: int = 0
    blocked_jobs: int = 0
    resolved_jobs: int = 0
    reused_jobs: int = 0


async def reconcile_once(
    engine: AsyncEngine,
    settings: Settings,
    registry: AnalysisRegistry | None = None,
) -> ReconcileCounts:
    """Run one finite reconciliation transaction and return transition counts."""
    async with engine.begin() as connection:
        return await reconcile_connection(connection, settings, registry)


async def reconcile_connection(
    connection: AsyncConnection,
    settings: Settings,
    registry: AnalysisRegistry | None = None,
) -> ReconcileCounts:
    queries = AsyncQuerier(connection)
    planned_jobs = (
        await _reconcile_automatic_plans(queries, registry, settings.batch_size)
        if registry is not None
        else 0
    )
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
        planned_jobs=planned_jobs,
        recovered_attempts=len(recovered),
        released_retries=len(released),
        blocked_jobs=len(blocked),
        resolved_jobs=resolved_count,
        reused_jobs=reused_count,
    )


async def _reconcile_automatic_plans(
    queries: AsyncQuerier,
    registry: AnalysisRegistry,
    batch_size: int,
) -> int:
    planned_jobs = 0
    for target_manifest in registry.automatic_plan():
        candidates = [
            row
            async for row in queries.list_uploaded_sources_missing_analysis(
                module_id=target_manifest.module_id,
                implementation_version=target_manifest.version,
                batch_size=batch_size,
            )
        ]
        for source in candidates:
            if source.sha256_hex is None:
                raise RuntimeError("uploaded source has no content identity")
            planned_jobs += await _ensure_automatic_analysis_plan(
                queries,
                registry,
                project_id=source.project_id,
                source_media_id=source.id,
                source_sha256=source.sha256_hex,
            )
    return planned_jobs


async def _ensure_automatic_analysis_plan(
    queries: AsyncQuerier,
    registry: AnalysisRegistry,
    *,
    project_id: UUID,
    source_media_id: UUID,
    source_sha256: str,
) -> int:
    jobs_by_module: dict[str, UUID] = {}
    created_jobs = 0
    for item in build_automatic_analysis_plan(registry, source_sha256=source_sha256):
        manifest = item.manifest
        definition = await queries.register_analysis_definition(
            RegisterAnalysisDefinitionParams(
                module_id=manifest.module_id,
                implementation_version=manifest.version,
                display_name=manifest.display_name,
                result_schema_version=manifest.result_schema_version,
                resource_class=models.AnalysisResourceClass(manifest.resource_class.value),
                automatic=manifest.automatic,
                manifest_hash=item.manifest_hash,
                manifest=item.manifest_document,
            )
        )
        if definition is None:
            raise RuntimeError("analysis definition registration returned no row")
        if definition.manifest_hash != item.manifest_hash:
            raise RuntimeError(
                "analysis definition version was reused with a different manifest: "
                f"{manifest.module_id}@{manifest.version}"
            )
        job = await queries.create_analysis_job(
            CreateAnalysisJobParams(
                id=uuid4(),
                project_id=project_id,
                source_media_id=source_media_id,
                module_id=manifest.module_id,
                implementation_version=manifest.version,
                parameters=item.parameters_document,
                request_key=item.request_key,
                cache_key=item.cache_key,
                priority=manifest.priority,
                max_attempts=manifest.max_attempts,
            )
        )
        if job is None:
            raise RuntimeError("automatic analysis job creation returned no row")
        created_jobs += int(job.created)
        jobs_by_module[manifest.module_id] = job.id
        for dependency in manifest.dependencies:
            await queries.add_analysis_job_dependency(
                project_id=project_id,
                job_id=job.id,
                depends_on_job_id=jobs_by_module[dependency],
            )
    return created_jobs


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
        try:
            expected = match_output_spec(dependency_manifest, row.output_name)
        except ValueError as exception:
            raise RuntimeError("dependency published an undeclared output") from exception
        if (
            expected.kind.value != row.artifact_kind
            or expected.media_type != row.artifact_media_type
            or expected.schema_id != row.artifact_schema_id
            or expected.schema_version != row.artifact_schema_version
        ):
            raise RuntimeError("dependency artifact metadata violates its manifest")
    for dependency, dependency_manifest in dependency_manifests.items():
        try:
            resolve_output_specs(dependency_manifest, outputs[dependency])
        except ValueError as exception:
            raise RuntimeError("dependency output set violates its manifest") from exception
    return analysis_cache_key(
        manifest_value,
        source_sha256=first.source_sha256,
        parameters=parameters,
        dependency_artifact_hashes=cast(dict[str, dict[str, str]], outputs),
    )
