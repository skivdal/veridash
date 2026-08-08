"""Idempotent creation of the server-owned automatic analysis DAG."""

import json
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncConnection
from veridash_analysis import (
    AnalysisRegistry,
    analysis_cache_key,
    analysis_request_key,
    manifest_document,
    manifest_hash,
)

from veridash_api.db.sqlc import models as database_models
from veridash_api.db.sqlc.analyses import (
    AsyncQuerier,
    CreateAutomaticAnalysisJobParams,
    RegisterAnalysisDefinitionParams,
)


async def create_automatic_analysis_dag(
    connection: AsyncConnection,
    registry: AnalysisRegistry,
    *,
    project_id: UUID,
    source_media_id: UUID,
    source_sha256: str,
) -> None:
    """Create every registered automatic node and edge exactly once."""
    queries = AsyncQuerier(connection)
    jobs_by_module: dict[str, UUID] = {}
    request_keys_by_module: dict[str, str] = {}

    for manifest in registry.automatic_plan():
        document = manifest_document(manifest)
        fingerprint = manifest_hash(manifest)
        definition = await queries.register_analysis_definition(
            RegisterAnalysisDefinitionParams(
                module_id=manifest.module_id,
                implementation_version=manifest.version,
                display_name=manifest.display_name,
                result_schema_version=manifest.result_schema_version,
                resource_class=database_models.AnalysisResourceClass(manifest.resource_class.value),
                automatic=manifest.automatic,
                manifest_hash=fingerprint,
                manifest=document,
            )
        )
        if definition is None:
            raise RuntimeError("analysis definition registration returned no row")
        if definition.manifest_hash != fingerprint:
            raise RuntimeError(
                "analysis definition version was reused with a different manifest: "
                f"{manifest.module_id}@{manifest.version}"
            )

        dependency_request_keys = {
            dependency: request_keys_by_module[dependency] for dependency in manifest.dependencies
        }
        request_key = analysis_request_key(
            manifest,
            source_sha256=source_sha256,
            parameters=manifest.default_parameters,
            dependency_request_keys=dependency_request_keys,
        )
        cache_key = None
        if not manifest.dependencies:
            cache_key = analysis_cache_key(
                manifest,
                source_sha256=source_sha256,
                parameters=manifest.default_parameters,
                dependency_artifact_hashes={},
            )
        job = await queries.create_automatic_analysis_job(
            CreateAutomaticAnalysisJobParams(
                id=uuid4(),
                project_id=project_id,
                source_media_id=source_media_id,
                module_id=manifest.module_id,
                implementation_version=manifest.version,
                parameters=json.dumps(
                    manifest.default_parameters,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                request_key=request_key,
                cache_key=cache_key,
                priority=manifest.priority,
                max_attempts=manifest.max_attempts,
            )
        )
        if job is None:
            raise RuntimeError("automatic analysis job creation returned no row")
        jobs_by_module[manifest.module_id] = job.id
        request_keys_by_module[manifest.module_id] = job.request_key

        for dependency in manifest.dependencies:
            await queries.add_automatic_analysis_dependency(
                project_id=project_id,
                job_id=job.id,
                depends_on_job_id=jobs_by_module[dependency],
            )
