"""Executable PostgreSQL state-machine coverage across scheduler and worker owners."""

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from veridash_analysis import AnalysisRegistry, manifest_document, manifest_hash
from veridash_analysis.modules import production_manifests
from veridash_analysis.probe_media import ProbeMediaModule
from veridash_analysis.synthetic import SyntheticAnalysisModule
from veridash_api.db.sqlc import models as api_models
from veridash_api.db.sqlc.analyses import AsyncQuerier as ApiAnalysisQuerier
from veridash_api.errors import ApiProblem
from veridash_api.services.analyses import (
    create_frame_stitch,
    get_project_analysis_blob_artifact,
    list_project_analysis_artifacts,
    retry_project_analysis,
)
from veridash_api.services.analysis_plans import create_automatic_analysis_dag
from veridash_core import ResourceClass
from veridash_scheduler.config import Settings as SchedulerSettings
from veridash_scheduler.db.sqlc import models as scheduler_models
from veridash_scheduler.db.sqlc.analysis import (
    AsyncQuerier as SchedulerAnalysisQuerier,
)
from veridash_scheduler.db.sqlc.analysis import (
    CreateAnalysisJobParams,
    RegisterAnalysisDefinitionParams,
)
from veridash_scheduler.reconcile import reconcile_connection, reconcile_once
from veridash_storage import FilesystemBlobStore
from veridash_worker.config import Settings as WorkerSettings
from veridash_worker.db.sqlc import models as worker_models
from veridash_worker.db.sqlc.attempts import AsyncQuerier as WorkerAttemptQuerier
from veridash_worker.db.sqlc.attempts import (
    ClaimReadyAnalysisJobParams,
    ClaimReadyAnalysisJobRow,
    FailAnalysisAttemptParams,
    ReportAnalysisAttemptProgressParams,
)
from veridash_worker.supervisor import claim_once, supervise_attempt


@pytest.mark.db
async def test_explicit_frame_stitch_is_idempotent_and_order_sensitive() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            transaction = await connection.begin_nested()
            user_id, project_id, media_id = await _create_uploaded_project(connection)
            registry = AnalysisRegistry(production_manifests())
            keyframe_manifest = registry.get("extract_keyframes")
            scheduler = SchedulerAnalysisQuerier(connection)
            registered = await scheduler.register_analysis_definition(
                RegisterAnalysisDefinitionParams(
                    module_id=keyframe_manifest.module_id,
                    implementation_version=keyframe_manifest.version,
                    display_name=keyframe_manifest.display_name,
                    result_schema_version=keyframe_manifest.result_schema_version,
                    resource_class=scheduler_models.AnalysisResourceClass.CPU,
                    automatic=True,
                    manifest_hash=manifest_hash(keyframe_manifest),
                    manifest=manifest_document(keyframe_manifest),
                )
            )
            assert registered is not None
            keyframe_job_id = await _create_job(
                scheduler,
                project_id=project_id,
                media_id=media_id,
                module_id="extract_keyframes",
                cache_character="d",
            )
            await scheduler.resolve_analysis_job_cache(
                job_id=keyframe_job_id,
                cache_key="d" * 64,
            )
            worker = WorkerAttemptQuerier(connection)
            attempt_id = uuid4()
            lease_token = uuid4()
            claimed = await worker.claim_ready_analysis_job(
                ClaimReadyAnalysisJobParams(
                    resource_class=worker_models.AnalysisResourceClass.CPU,
                    attempt_id=attempt_id,
                    worker_id="frame-stitch-api-test",
                    lease_token=lease_token,
                    lease_seconds=60,
                )
            )
            assert claimed is not None
            assert claimed.job_id == keyframe_job_id
            for ordinal, digest in ((1, "e" * 64), (2, "f" * 64)):
                artifact_id = uuid4()
                await connection.execute(
                    text(
                        """
                        INSERT INTO analysis_artifact (
                            id, producer_attempt_id, kind, sha256_hex, size_bytes,
                            media_type, blob_key, schema_id, schema_version
                        )
                        VALUES (
                            :artifact_id, :attempt_id, 'blob', :digest, 4,
                            'image/jpeg', :digest, 'veridash.keyframe.jpeg', 1
                        )
                        """
                    ),
                    {
                        "artifact_id": artifact_id,
                        "attempt_id": attempt_id,
                        "digest": digest,
                    },
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO analysis_job_artifact (job_id, artifact_id, output_name)
                        VALUES (:job_id, :artifact_id, :output_name)
                        """
                    ),
                    {
                        "job_id": keyframe_job_id,
                        "artifact_id": artifact_id,
                        "output_name": f"frames_{ordinal:06d}",
                    },
                )
            completed = await worker.complete_analysis_attempt(
                attempt_id=attempt_id,
                lease_token=lease_token,
            )
            assert completed is not None

            reverse = await create_frame_stitch(
                connection,
                registry,
                user_id=user_id,
                project_id=project_id,
                selected_output_names=["frames_000002", "frames_000001"],
            )
            duplicate = await create_frame_stitch(
                connection,
                registry,
                user_id=user_id,
                project_id=project_id,
                selected_output_names=["frames_000002", "frames_000001"],
            )
            forward = await create_frame_stitch(
                connection,
                registry,
                user_id=user_id,
                project_id=project_id,
                selected_output_names=["frames_000001", "frames_000002"],
            )

            assert reverse.id == duplicate.id
            assert reverse.id != forward.id
            assert reverse.module_id == "stitch_frames"
            assert reverse.parameters["selected_output_names"] == [
                "frames_000002",
                "frames_000001",
            ]
            persisted = (
                await connection.execute(
                    text(
                        """
                        SELECT request_key, cache_key
                        FROM analysis_job
                        WHERE id IN (:reverse_id, :forward_id)
                        ORDER BY id
                        """
                    ),
                    {"reverse_id": reverse.id, "forward_id": forward.id},
                )
            ).all()
            assert len(persisted) == 2
            assert persisted[0].request_key != persisted[1].request_key
            assert persisted[0].cache_key != persisted[1].cache_key
            dependencies = (
                await connection.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM analysis_job_dependency
                        WHERE job_id = :job_id AND depends_on_job_id = :dependency_id
                        """
                    ),
                    {"job_id": reverse.id, "dependency_id": keyframe_job_id},
                )
            ).scalar_one()
            assert dependencies == 1
            created_events = (
                await connection.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM project_event
                        WHERE job_id = :job_id AND event_type = 'job.created'
                        """
                    ),
                    {"job_id": reverse.id},
                )
            ).scalar_one()
            assert created_events == 1
            await transaction.rollback()
    finally:
        await engine.dispose()


async def _create_uploaded_project(connection: AsyncConnection) -> tuple[int, UUID, UUID]:
    user = await connection.execute(
        text(
            """
            INSERT INTO app_user (username, password_hash)
            VALUES (:username, :password_hash)
            RETURNING id
            """
        ),
        {
            "username": f"analysis-state-test-{uuid4().hex}",
            "password_hash": "not-a-real-password-hash",
        },
    )
    user_id = user.scalar_one()
    project_id = uuid4()
    media_id = uuid4()
    source_hash = "a" * 64
    await connection.execute(
        text(
            """
            INSERT INTO project (id, user_id, title)
            VALUES (:project_id, :user_id, 'Analysis state test')
            """
        ),
        {"project_id": project_id, "user_id": user_id},
    )
    await connection.execute(
        text(
            """
            INSERT INTO source_media (
                id,
                project_id,
                upload_state,
                original_filename,
                media_type,
                size_bytes,
                sha256_hex,
                blob_key,
                uploaded_at
            )
            VALUES (
                :media_id,
                :project_id,
                'uploaded',
                'source.mp4',
                'video/mp4',
                1,
                :source_hash,
                :source_hash,
                now()
            )
            """
        ),
        {"media_id": media_id, "project_id": project_id, "source_hash": source_hash},
    )
    return user_id, project_id, media_id


def _tiny_video(path: Path) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg and ffprobe are required for probe integration")
    subprocess.run(
        (
            ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=16x16:d=0.2",
            "-an",
            "-c:v",
            "mpeg4",
            "-y",
            str(path),
        ),
        check=True,
    )
    return path.read_bytes()


async def _byte_chunks(content: bytes) -> AsyncIterator[bytes]:
    yield content


async def _register_definition(
    queries: SchedulerAnalysisQuerier,
    module_id: str,
    dependencies: list[str],
) -> None:
    manifest = json.dumps(
        {
            "module_id": module_id,
            "display_name": module_id.replace("_", " ").title(),
            "version": "1.0.0",
            "result_schema_version": 1,
            "resource_class": "cpu",
            "dependencies": dependencies,
            "automatic": True,
            "progress_stages": [],
            "outputs": [
                {
                    "name": "result",
                    "kind": "json",
                    "media_type": "application/json",
                    "schema_id": f"veridash.{module_id}",
                    "schema_version": 1,
                }
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    definition = await queries.register_analysis_definition(
        RegisterAnalysisDefinitionParams(
            module_id=module_id,
            implementation_version="1.0.0",
            display_name=module_id.replace("_", " ").title(),
            result_schema_version=1,
            resource_class=scheduler_models.AnalysisResourceClass.CPU,
            automatic=True,
            manifest_hash=hashlib.sha256(manifest.encode()).hexdigest(),
            manifest=manifest,
        )
    )
    assert definition is not None


async def _create_job(
    queries: SchedulerAnalysisQuerier,
    *,
    project_id: UUID,
    media_id: UUID,
    module_id: str,
    cache_character: str,
    max_attempts: int = 2,
    cache_known: bool = True,
) -> UUID:
    job = await queries.create_analysis_job(
        CreateAnalysisJobParams(
            id=uuid4(),
            project_id=project_id,
            source_media_id=media_id,
            module_id=module_id,
            implementation_version="1.0.0",
            parameters="{}",
            request_key=cache_character * 64,
            cache_key=cache_character * 64 if cache_known else None,
            priority=0,
            max_attempts=max_attempts,
        )
    )
    assert job is not None
    return job.id


@pytest.mark.db
async def test_analysis_dag_progress_retry_and_events_are_durable() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            transaction = await connection.begin_nested()
            user_id, project_id, media_id = await _create_uploaded_project(connection)
            scheduler = SchedulerAnalysisQuerier(connection)
            for module_id, dependencies in (
                ("probe_media", []),
                ("extract_coordinates", ["probe_media"]),
                ("map_context", ["extract_coordinates"]),
            ):
                await _register_definition(scheduler, module_id, dependencies)

            probe_job_id = await _create_job(
                scheduler,
                project_id=project_id,
                media_id=media_id,
                module_id="probe_media",
                cache_character="1",
            )
            coordinates_job_id = await _create_job(
                scheduler,
                project_id=project_id,
                media_id=media_id,
                module_id="extract_coordinates",
                cache_character="2",
                cache_known=False,
            )
            map_job_id = await _create_job(
                scheduler,
                project_id=project_id,
                media_id=media_id,
                module_id="map_context",
                cache_character="3",
                cache_known=False,
            )
            await scheduler.add_analysis_job_dependency(
                project_id=project_id,
                job_id=coordinates_job_id,
                depends_on_job_id=probe_job_id,
            )
            await scheduler.add_analysis_job_dependency(
                project_id=project_id,
                job_id=map_job_id,
                depends_on_job_id=coordinates_job_id,
            )

            scheduler_settings = SchedulerSettings(
                database_url=database_url,
                batch_size=20,
                worker_lost_retry_delay_seconds=0,
            )
            initial_reconcile = await reconcile_connection(connection, scheduler_settings)
            assert initial_reconcile.resolved_jobs == 1

            worker = WorkerAttemptQuerier(connection)
            first_attempt_id = uuid4()
            first_lease_token = uuid4()
            claimed_probe = await worker.claim_ready_analysis_job(
                ClaimReadyAnalysisJobParams(
                    resource_class=worker_models.AnalysisResourceClass.CPU,
                    attempt_id=first_attempt_id,
                    worker_id="cpu-worker-1",
                    lease_token=first_lease_token,
                    lease_seconds=60,
                )
            )
            assert claimed_probe is not None
            assert claimed_probe.job_id == probe_job_id
            assert claimed_probe.attempt_number == 1

            progress = await worker.report_analysis_attempt_progress(
                ReportAnalysisAttemptProgressParams(
                    lease_seconds=60,
                    progress_stage="probing",
                    progress_completed=1,
                    progress_total=2,
                    progress_message="Reading streams",
                    attempt_id=first_attempt_id,
                    lease_token=first_lease_token,
                )
            )
            assert progress is not None
            assert progress.progress_completed == 1
            stale_progress = await worker.report_analysis_attempt_progress(
                ReportAnalysisAttemptProgressParams(
                    lease_seconds=60,
                    progress_stage="probing",
                    progress_completed=2,
                    progress_total=2,
                    progress_message=None,
                    attempt_id=first_attempt_id,
                    lease_token=uuid4(),
                )
            )
            assert stale_progress is None

            artifact_id = uuid4()
            await connection.execute(
                text(
                    """
                    INSERT INTO analysis_artifact (
                        id,
                        producer_attempt_id,
                        kind,
                        sha256_hex,
                        size_bytes,
                        media_type,
                        json_payload,
                        schema_id,
                        schema_version
                    )
                    VALUES (
                        :artifact_id,
                        :attempt_id,
                        'json',
                        :sha256,
                        2,
                        'application/json',
                        '{}'::jsonb,
                        'veridash.probe_media',
                        1
                    )
                    """
                ),
                {
                    "artifact_id": artifact_id,
                    "attempt_id": first_attempt_id,
                    "sha256": "b" * 64,
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO analysis_job_artifact (job_id, artifact_id, output_name)
                    VALUES (:job_id, :artifact_id, 'result')
                    """
                ),
                {"job_id": probe_job_id, "artifact_id": artifact_id},
            )

            completed_probe = await worker.complete_analysis_attempt(
                attempt_id=first_attempt_id,
                lease_token=first_lease_token,
            )
            assert completed_probe is not None
            assert completed_probe.state == worker_models.AnalysisJobState.SUCCEEDED

            second_user_id, second_project_id, second_media_id = await _create_uploaded_project(
                connection
            )
            reused_probe_job_id = await _create_job(
                scheduler,
                project_id=second_project_id,
                media_id=second_media_id,
                module_id="probe_media",
                cache_character="1",
            )

            next_reconcile = await reconcile_connection(connection, scheduler_settings)
            assert next_reconcile.resolved_jobs == 2
            assert next_reconcile.reused_jobs == 1
            reused_jobs = [
                row
                async for row in ApiAnalysisQuerier(connection).list_project_analysis_jobs(
                    project_id=second_project_id,
                    user_id=second_user_id,
                )
            ]
            assert len(reused_jobs) == 1
            assert reused_jobs[0].id == reused_probe_job_id
            assert reused_jobs[0].reused_from_job_id == probe_job_id
            assert reused_jobs[0].state == api_models.AnalysisJobState.SUCCEEDED

            retry_attempt_id = uuid4()
            retry_lease_token = uuid4()
            claimed_coordinates = await worker.claim_ready_analysis_job(
                ClaimReadyAnalysisJobParams(
                    resource_class=worker_models.AnalysisResourceClass.CPU,
                    attempt_id=retry_attempt_id,
                    worker_id="cpu-worker-1",
                    lease_token=retry_lease_token,
                    lease_seconds=60,
                )
            )
            assert claimed_coordinates is not None
            assert claimed_coordinates.job_id == coordinates_job_id

            retry_wait = await worker.fail_analysis_attempt(
                FailAnalysisAttemptParams(
                    attempt_id=retry_attempt_id,
                    lease_token=retry_lease_token,
                    error_kind=worker_models.AnalysisErrorKind.TRANSIENT_INFRASTRUCTURE,
                    public_error_message="A temporary worker error occurred.",
                    diagnostic_id=uuid4(),
                    diagnostic_details=json.dumps({"test": True}),
                    retry_delay_seconds=0,
                )
            )
            assert retry_wait is not None
            assert retry_wait.state == worker_models.AnalysisJobState.RETRY_WAIT

            retry_reconcile = await reconcile_connection(connection, scheduler_settings)
            assert retry_reconcile.released_retries == 1

            final_attempt_id = uuid4()
            final_lease_token = uuid4()
            claimed_retry = await worker.claim_ready_analysis_job(
                ClaimReadyAnalysisJobParams(
                    resource_class=worker_models.AnalysisResourceClass.CPU,
                    attempt_id=final_attempt_id,
                    worker_id="cpu-worker-1",
                    lease_token=final_lease_token,
                    lease_seconds=60,
                )
            )
            assert claimed_retry is not None
            assert claimed_retry.attempt_number == 2

            terminal_failure = await worker.fail_analysis_attempt(
                FailAnalysisAttemptParams(
                    attempt_id=final_attempt_id,
                    lease_token=final_lease_token,
                    error_kind=worker_models.AnalysisErrorKind.INVALID_INPUT,
                    public_error_message="No coordinates were present.",
                    diagnostic_id=None,
                    diagnostic_details=None,
                    retry_delay_seconds=300,
                )
            )
            assert terminal_failure is not None
            assert terminal_failure.state == worker_models.AnalysisJobState.FAILED
            assert terminal_failure.next_attempt_at is None

            failure_reconcile = await reconcile_connection(connection, scheduler_settings)
            assert failure_reconcile.blocked_jobs == 1

            await _register_definition(scheduler, "lost_worker", [])
            lost_job_id = await _create_job(
                scheduler,
                project_id=project_id,
                media_id=media_id,
                module_id="lost_worker",
                cache_character="4",
                max_attempts=1,
            )
            lost_ready = await reconcile_connection(connection, scheduler_settings)
            assert lost_ready.resolved_jobs == 1
            lost_attempt_id = uuid4()
            lost_lease_token = uuid4()
            claimed_lost_job = await worker.claim_ready_analysis_job(
                ClaimReadyAnalysisJobParams(
                    resource_class=worker_models.AnalysisResourceClass.CPU,
                    attempt_id=lost_attempt_id,
                    worker_id="cpu-worker-2",
                    lease_token=lost_lease_token,
                    lease_seconds=60,
                )
            )
            assert claimed_lost_job is not None
            assert claimed_lost_job.job_id == lost_job_id
            await connection.execute(
                text(
                    """
                    UPDATE analysis_job_attempt
                    SET lease_expires_at = now() - interval '1 second'
                    WHERE id = :attempt_id
                    """
                ),
                {"attempt_id": lost_attempt_id},
            )
            recovered_lost_job = await reconcile_connection(connection, scheduler_settings)
            assert recovered_lost_job.recovered_attempts == 1

            await _register_definition(scheduler, "canceled_worker", [])
            canceled_job_id = await _create_job(
                scheduler,
                project_id=project_id,
                media_id=media_id,
                module_id="canceled_worker",
                cache_character="5",
                max_attempts=2,
            )
            canceled_ready = await reconcile_connection(connection, scheduler_settings)
            assert canceled_ready.resolved_jobs == 1
            canceled_attempt_id = uuid4()
            canceled_lease_token = uuid4()
            claimed_canceled_job = await worker.claim_ready_analysis_job(
                ClaimReadyAnalysisJobParams(
                    resource_class=worker_models.AnalysisResourceClass.CPU,
                    attempt_id=canceled_attempt_id,
                    worker_id="cpu-worker-3",
                    lease_token=canceled_lease_token,
                    lease_seconds=60,
                )
            )
            assert claimed_canceled_job is not None
            assert claimed_canceled_job.job_id == canceled_job_id
            await connection.execute(
                text(
                    """
                    UPDATE analysis_job
                    SET cancel_requested_at = now()
                    WHERE id = :job_id
                    """
                ),
                {"job_id": canceled_job_id},
            )
            await connection.execute(
                text(
                    """
                    UPDATE analysis_job_attempt
                    SET lease_expires_at = now() - interval '1 second'
                    WHERE id = :attempt_id
                    """
                ),
                {"attempt_id": canceled_attempt_id},
            )
            recovered_cancellation = await reconcile_connection(connection, scheduler_settings)
            assert recovered_cancellation.recovered_attempts == 1

            api_queries = ApiAnalysisQuerier(connection)
            jobs = [
                row
                async for row in api_queries.list_project_analysis_jobs(
                    project_id=project_id,
                    user_id=user_id,
                )
            ]
            assert {row.module_id: row.state for row in jobs} == {
                "probe_media": api_models.AnalysisJobState.SUCCEEDED,
                "extract_coordinates": api_models.AnalysisJobState.FAILED,
                "map_context": api_models.AnalysisJobState.BLOCKED,
                "lost_worker": api_models.AnalysisJobState.FAILED,
                "canceled_worker": api_models.AnalysisJobState.CANCELED,
            }
            attempts = [
                row
                async for row in api_queries.list_project_analysis_attempts(
                    project_id=project_id,
                    user_id=user_id,
                )
            ]
            attempt_numbers_by_job: dict[UUID, list[int]] = {}
            for attempt in attempts:
                attempt_numbers_by_job.setdefault(attempt.job_id, []).append(attempt.attempt_number)
            assert attempt_numbers_by_job == {
                probe_job_id: [1],
                coordinates_job_id: [1, 2],
                lost_job_id: [1],
                canceled_job_id: [1],
            }
            events = [
                row
                async for row in api_queries.list_project_events_after(
                    project_id=project_id,
                    user_id=user_id,
                    after_event_id=0,
                    batch_size=100,
                )
            ]
            assert [event.id for event in events] == sorted(event.id for event in events)
            assert {event.event_type for event in events}.issuperset(
                {"job.created", "job.state_changed", "job.progress", "job.error"}
            )
            retried = await retry_project_analysis(
                connection,
                user_id=user_id,
                project_id=project_id,
                job_id=coordinates_job_id,
            )
            assert retried.state == "waiting_for_dependencies"
            assert retried.max_attempts == 3
            restored_jobs = [
                row
                async for row in api_queries.list_project_analysis_jobs(
                    project_id=project_id,
                    user_id=user_id,
                )
            ]
            assert {
                row.module_id: row.state
                for row in restored_jobs
                if row.module_id in {"extract_coordinates", "map_context"}
            } == {
                "extract_coordinates": api_models.AnalysisJobState.WAITING_FOR_DEPENDENCIES,
                "map_context": api_models.AnalysisJobState.WAITING_FOR_DEPENDENCIES,
            }
            await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_supervisor_isolates_child_and_atomically_publishes_result(
    tmp_path: Path,
) -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_async_engine(database_url)
    user_id: int | None = None
    project_id: UUID | None = None
    try:
        manifest = SyntheticAnalysisModule.manifest
        async with engine.begin() as connection:
            user_id, project_id, media_id = await _create_uploaded_project(connection)
            scheduler = SchedulerAnalysisQuerier(connection)
            registered = await scheduler.register_analysis_definition(
                RegisterAnalysisDefinitionParams(
                    module_id=manifest.module_id,
                    implementation_version=manifest.version,
                    display_name=manifest.display_name,
                    result_schema_version=manifest.result_schema_version,
                    resource_class=scheduler_models.AnalysisResourceClass.CPU,
                    automatic=manifest.automatic,
                    manifest_hash=manifest_hash(manifest),
                    manifest=manifest_document(manifest),
                )
            )
            assert registered is not None
            job_id = await _create_job(
                scheduler,
                project_id=project_id,
                media_id=media_id,
                module_id=manifest.module_id,
                cache_character="6",
            )
            await connection.execute(
                text("UPDATE analysis_job SET parameters = :parameters WHERE id = :job_id"),
                {
                    "job_id": job_id,
                    "parameters": json.dumps({"steps": 2, "fail_attempts": 1}),
                },
            )

        scheduler_settings = SchedulerSettings(
            database_url=database_url,
            worker_lost_retry_delay_seconds=0,
        )
        worker_settings = WorkerSettings(
            database_url=database_url,
            data_root=tmp_path / "data",
            lease_seconds=30,
            heartbeat_interval_seconds=0.1,
            retry_delay_seconds=0,
        )
        assert (await reconcile_once(engine, scheduler_settings)).resolved_jobs == 1

        first_claim = await claim_once(
            engine,
            resource_class=ResourceClass.CPU,
            worker_id="supervisor-integration-test",
            settings=worker_settings,
        )
        assert first_claim is not None
        first_outcome = await supervise_attempt(engine, first_claim, worker_settings)
        assert first_outcome.state == "retry_wait"

        assert (await reconcile_once(engine, scheduler_settings)).released_retries == 1
        second_claim = await claim_once(
            engine,
            resource_class=ResourceClass.CPU,
            worker_id="supervisor-integration-test",
            settings=worker_settings,
        )
        assert second_claim is not None
        second_outcome = await supervise_attempt(engine, second_claim, worker_settings)
        assert second_outcome.state == "succeeded"

        async with engine.begin() as connection:
            scheduler = SchedulerAnalysisQuerier(connection)
            canceled_job_id = await _create_job(
                scheduler,
                project_id=project_id,
                media_id=media_id,
                module_id=manifest.module_id,
                cache_character="7",
            )
            await connection.execute(
                text("UPDATE analysis_job SET parameters = :parameters WHERE id = :job_id"),
                {
                    "job_id": canceled_job_id,
                    "parameters": json.dumps({"steps": 5, "delay_seconds": 1}),
                },
            )
        assert (await reconcile_once(engine, scheduler_settings)).resolved_jobs == 1
        canceled_claim = await claim_once(
            engine,
            resource_class=ResourceClass.CPU,
            worker_id="supervisor-cancellation-test",
            settings=worker_settings,
        )
        assert canceled_claim is not None
        cancellation_run = asyncio.create_task(
            supervise_attempt(engine, canceled_claim, worker_settings)
        )
        await asyncio.sleep(0.05)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE analysis_job
                    SET cancel_requested_at = now()
                    WHERE id = :job_id
                    """
                ),
                {"job_id": canceled_job_id},
            )
        canceled_outcome = await cancellation_run
        assert canceled_outcome.state == "canceled"

        async with engine.connect() as connection:
            job = (
                await connection.execute(
                    text(
                        """
                        SELECT state, winning_attempt_id
                        FROM analysis_job
                        WHERE id = :job_id
                        """
                    ),
                    {"job_id": job_id},
                )
            ).one()
            assert job.state == "succeeded"
            assert job.winning_attempt_id == second_claim.id
            attempts = (
                await connection.execute(
                    text(
                        """
                        SELECT attempt_number, state, progress_completed, progress_total
                        FROM analysis_job_attempt
                        WHERE job_id = :job_id
                        ORDER BY attempt_number
                        """
                    ),
                    {"job_id": job_id},
                )
            ).all()
            assert [attempt.state for attempt in attempts] == ["failed", "succeeded"]
            assert attempts[1].progress_completed == 2
            assert attempts[1].progress_total == 2
            artifact = (
                await connection.execute(
                    text(
                        """
                        SELECT a.kind, a.media_type, a.json_payload, a.schema_id
                        FROM analysis_artifact AS a
                        JOIN analysis_job_artifact AS output ON output.artifact_id = a.id
                        WHERE output.job_id = :job_id AND output.output_name = 'result'
                        """
                    ),
                    {"job_id": job_id},
                )
            ).one()
            assert artifact.kind == "json"
            assert artifact.media_type == "application/json"
            assert artifact.json_payload == {
                "steps_completed": 2,
                "deterministic_value": "synthetic:2",
            }
            assert artifact.schema_id == "veridash.synthetic_test"
            canceled_attempt = (
                await connection.execute(
                    text(
                        """
                        SELECT state, error_kind
                        FROM analysis_job_attempt
                        WHERE job_id = :job_id
                        """
                    ),
                    {"job_id": canceled_job_id},
                )
            ).one()
            assert canceled_attempt.state == "canceled"
            assert canceled_attempt.error_kind == "canceled"
            canceled_artifacts = await connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM analysis_job_artifact
                    WHERE job_id = :job_id
                    """
                ),
                {"job_id": canceled_job_id},
            )
            assert canceled_artifacts == 0
    finally:
        if project_id is not None:
            async with engine.begin() as connection:
                cleanup_statements = (
                    "DELETE FROM project_event WHERE project_id = :project_id",
                    "DELETE FROM project_analysis_result WHERE project_id = :project_id",
                    "DELETE FROM analysis_job_dependency WHERE project_id = :project_id",
                    """
                    DELETE FROM analysis_job_artifact
                    WHERE job_id IN (
                        SELECT id FROM analysis_job WHERE project_id = :project_id
                    )
                    """,
                    """
                    DELETE FROM analysis_artifact
                    WHERE producer_attempt_id IN (
                        SELECT id FROM analysis_job_attempt WHERE project_id = :project_id
                    )
                    """,
                    """
                    UPDATE analysis_job
                    SET
                        state = 'failed',
                        winning_attempt_id = NULL,
                        failure_kind = 'internal_bug',
                        public_failure_message = 'test cleanup',
                        finished_at = now()
                    WHERE project_id = :project_id AND state = 'succeeded'
                    """,
                    "DELETE FROM analysis_job WHERE project_id = :project_id",
                    "DELETE FROM source_media WHERE project_id = :project_id",
                    "DELETE FROM project WHERE id = :project_id",
                )
                for statement in cleanup_statements:
                    await connection.execute(text(statement), {"project_id": project_id})
                if user_id is not None:
                    await connection.execute(
                        text("DELETE FROM app_user WHERE id = :user_id"),
                        {"user_id": user_id},
                    )
                await connection.execute(
                    text(
                        """
                        DELETE FROM analysis_definition
                        WHERE module_id = 'synthetic_test'
                            AND implementation_version = '1.0.0'
                        """
                    )
                )
        await engine.dispose()


@pytest.mark.db
async def test_real_source_analyses_publish_json_and_blob_artifacts(tmp_path: Path) -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_async_engine(database_url)
    store = FilesystemBlobStore(tmp_path / "data")
    user_id: int | None = None
    project_id: UUID | None = None
    try:
        content = _tiny_video(tmp_path / "probe-source.mp4")
        async with engine.begin() as connection:
            user_id, project_id, media_id = await _create_uploaded_project(connection)
        await store.stage(str(media_id), _byte_chunks(content), max_bytes=len(content) + 1)
        blob = store.publish(store.staging_path(str(media_id)), media_type="video/mp4")
        registry = AnalysisRegistry((ProbeMediaModule.manifest,))
        production_registry = AnalysisRegistry(production_manifests())
        assert [manifest.module_id for manifest in production_registry.automatic_plan()] == [
            "probe_media",
            "extract_coordinates",
            "extract_keyframes",
            "transcribe",
            "translate_transcript",
        ]
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE source_media
                    SET
                        size_bytes = :size_bytes,
                        sha256_hex = :sha256,
                        blob_key = :sha256
                    WHERE id = :media_id
                    """
                ),
                {
                    "media_id": media_id,
                    "size_bytes": blob.size_bytes,
                    "sha256": blob.sha256,
                },
            )
            await create_automatic_analysis_dag(
                connection,
                registry,
                project_id=project_id,
                source_media_id=media_id,
                source_sha256=blob.sha256,
            )

        scheduler_settings = SchedulerSettings(database_url=database_url)
        reconciled = await reconcile_once(
            engine,
            scheduler_settings,
            production_registry,
        )
        assert reconciled.planned_jobs == 4
        assert reconciled.resolved_jobs == 3
        assert (
            await reconcile_once(engine, scheduler_settings, production_registry)
        ).planned_jobs == 0
        worker_settings = WorkerSettings(
            database_url=database_url,
            data_root=tmp_path / "data",
            lease_seconds=30,
            heartbeat_interval_seconds=0.1,
        )
        claims: dict[str, ClaimReadyAnalysisJobRow] = {}
        for _ in range(2):
            claim = await claim_once(
                engine,
                resource_class=ResourceClass.CPU,
                worker_id="source-analysis-integration-test",
                settings=worker_settings,
            )
            assert claim is not None
            claims[claim.module_id] = claim
            outcome = await supervise_attempt(engine, claim, worker_settings)
            assert outcome.state == "succeeded"
        dependency_reconcile = await reconcile_once(
            engine,
            scheduler_settings,
            production_registry,
        )
        assert dependency_reconcile.resolved_jobs == 1
        coordinate_claim = await claim_once(
            engine,
            resource_class=ResourceClass.CPU,
            worker_id="source-analysis-integration-test",
            settings=worker_settings,
        )
        assert coordinate_claim is not None
        claims[coordinate_claim.module_id] = coordinate_claim
        coordinate_outcome = await supervise_attempt(engine, coordinate_claim, worker_settings)
        assert coordinate_outcome.state == "succeeded"
        assert set(claims) == {"extract_keyframes", "probe_media", "extract_coordinates"}
        probe_claim = claims["probe_media"]
        frames_claim = claims["extract_keyframes"]
        coordinates_claim = claims["extract_coordinates"]

        async with engine.connect() as connection:
            assert user_id is not None
            authorized_artifacts = await list_project_analysis_artifacts(
                connection,
                user_id=user_id,
                project_id=project_id,
                job_id=probe_claim.job_id,
            )
            assert len(authorized_artifacts) == 1
            assert authorized_artifacts[0].schema_id == "veridash.probe_media.raw"
            artifact = (
                await connection.execute(
                    text(
                        """
                        SELECT artifact.json_payload, artifact.schema_id
                        FROM analysis_artifact AS artifact
                        JOIN analysis_job_artifact AS output
                            ON output.artifact_id = artifact.id
                        WHERE output.job_id = :job_id AND output.output_name = 'result'
                        """
                    ),
                    {"job_id": probe_claim.job_id},
                )
            ).one()
            assert artifact.schema_id == "veridash.probe_media.raw"
            assert artifact.json_payload["source_sha256"] == blob.sha256
            assert any(
                stream.get("codec_type") == "video"
                for stream in artifact.json_payload["probe"]["streams"]
            )
            frame_artifacts = await list_project_analysis_artifacts(
                connection,
                user_id=user_id,
                project_id=project_id,
                job_id=frames_claim.job_id,
            )
            assert [item.output_name for item in frame_artifacts] == [
                "frames_000001",
                "index",
            ]
            frame = frame_artifacts[0]
            assert frame.kind == "blob"
            assert frame.schema_id == "veridash.keyframe.jpeg"
            assert store.exists(frame.sha256_hex)
            authorized_frame = await get_project_analysis_blob_artifact(
                connection,
                user_id=user_id,
                project_id=project_id,
                job_id=frames_claim.job_id,
                artifact_id=frame.id,
            )
            assert authorized_frame.sha256_hex == frame.sha256_hex
            with pytest.raises(ApiProblem) as hidden:
                await get_project_analysis_blob_artifact(
                    connection,
                    user_id=-1,
                    project_id=project_id,
                    job_id=frames_claim.job_id,
                    artifact_id=frame.id,
                )
            assert hidden.value.status == 404
            with store.open(frame.sha256_hex) as content_file:
                assert content_file.read(2) == b"\xff\xd8"
            index = frame_artifacts[1].json_payload
            assert isinstance(index, dict)
            indexed_frames = index["frames"]
            assert isinstance(indexed_frames, list)
            first_frame = indexed_frames[0]
            assert isinstance(first_frame, dict)
            assert first_frame["output_name"] == "frames_000001"
            coordinate_artifacts = await list_project_analysis_artifacts(
                connection,
                user_id=user_id,
                project_id=project_id,
                job_id=coordinates_claim.job_id,
            )
            assert len(coordinate_artifacts) == 1
            assert coordinate_artifacts[0].schema_id == "veridash.coordinates.embedded"
            assert coordinate_artifacts[0].json_payload == {
                "status": "not_found",
                "latitude": None,
                "longitude": None,
                "altitude_meters": None,
                "candidates": [],
            }
        for claim in claims.values():
            assert not (tmp_path / "data" / "staging" / "attempts" / str(claim.id)).exists()
    finally:
        if project_id is not None:
            async with engine.begin() as connection:
                for statement in (
                    "DELETE FROM project_event WHERE project_id = :project_id",
                    "DELETE FROM project_analysis_result WHERE project_id = :project_id",
                    "DELETE FROM analysis_job_dependency WHERE project_id = :project_id",
                    """
                    DELETE FROM analysis_job_artifact
                    WHERE job_id IN (
                        SELECT id FROM analysis_job WHERE project_id = :project_id
                    )
                    """,
                    """
                    DELETE FROM analysis_artifact
                    WHERE producer_attempt_id IN (
                        SELECT id FROM analysis_job_attempt WHERE project_id = :project_id
                    )
                    """,
                    """
                    UPDATE analysis_job
                    SET
                        state = 'failed',
                        winning_attempt_id = NULL,
                        failure_kind = 'internal_bug',
                        public_failure_message = 'test cleanup',
                        finished_at = now()
                    WHERE project_id = :project_id AND state = 'succeeded'
                    """,
                    "DELETE FROM analysis_job WHERE project_id = :project_id",
                    "DELETE FROM source_media WHERE project_id = :project_id",
                    "DELETE FROM project WHERE id = :project_id",
                ):
                    await connection.execute(text(statement), {"project_id": project_id})
                if user_id is not None:
                    await connection.execute(
                        text("DELETE FROM app_user WHERE id = :user_id"),
                        {"user_id": user_id},
                    )
                await connection.execute(
                    text(
                        """
                        DELETE FROM analysis_definition
                        WHERE module_id IN (
                            'probe_media',
                            'extract_keyframes',
                            'extract_coordinates',
                            'transcribe',
                            'translate_transcript'
                        )
                            AND implementation_version = '1.0.0'
                        """
                    )
                )
        await engine.dispose()
