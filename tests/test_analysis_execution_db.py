"""Executable PostgreSQL state-machine coverage across scheduler and worker owners."""

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from veridash_api.db.sqlc import models as api_models
from veridash_api.db.sqlc.analyses import AsyncQuerier as ApiAnalysisQuerier
from veridash_scheduler.db.sqlc import models as scheduler_models
from veridash_scheduler.db.sqlc.analysis import (
    AsyncQuerier as SchedulerAnalysisQuerier,
)
from veridash_scheduler.db.sqlc.analysis import (
    CreateAnalysisJobParams,
    RegisterAnalysisDefinitionParams,
)
from veridash_worker.db.sqlc import models as worker_models
from veridash_worker.db.sqlc.attempts import AsyncQuerier as WorkerAttemptQuerier
from veridash_worker.db.sqlc.attempts import (
    ClaimReadyAnalysisJobParams,
    FailAnalysisAttemptParams,
    ReportAnalysisAttemptProgressParams,
)


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
) -> UUID:
    job = await queries.create_analysis_job(
        CreateAnalysisJobParams(
            id=uuid4(),
            project_id=project_id,
            source_media_id=media_id,
            module_id=module_id,
            implementation_version="1.0.0",
            parameters="{}",
            cache_key=cache_character * 64,
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
            )
            map_job_id = await _create_job(
                scheduler,
                project_id=project_id,
                media_id=media_id,
                module_id="map_context",
                cache_character="3",
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

            initially_ready = [
                row async for row in scheduler.resolve_ready_analysis_jobs(batch_size=20)
            ]
            assert [row.id for row in initially_ready] == [probe_job_id]

            worker = WorkerAttemptQuerier(connection)
            first_attempt_id = uuid4()
            first_lease_token = uuid4()
            claimed_probe = await worker.claim_ready_analysis_job(
                ClaimReadyAnalysisJobParams(
                    resource_class=worker_models.AnalysisResourceClass.CPU,
                    attempt_id=first_attempt_id,
                    worker_id="cpu-worker-1",
                    lease_token=first_lease_token,
                    lease_expires_at=datetime.now(UTC) + timedelta(minutes=1),
                )
            )
            assert claimed_probe is not None
            assert claimed_probe.job_id == probe_job_id
            assert claimed_probe.attempt_number == 1

            progress = await worker.report_analysis_attempt_progress(
                ReportAnalysisAttemptProgressParams(
                    lease_expires_at=datetime.now(UTC) + timedelta(minutes=1),
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
                    lease_expires_at=datetime.now(UTC) + timedelta(minutes=1),
                    progress_stage="probing",
                    progress_completed=2,
                    progress_total=2,
                    progress_message=None,
                    attempt_id=first_attempt_id,
                    lease_token=uuid4(),
                )
            )
            assert stale_progress is None

            completed_probe = await worker.complete_analysis_attempt(
                attempt_id=first_attempt_id,
                lease_token=first_lease_token,
            )
            assert completed_probe is not None
            assert completed_probe.state == worker_models.AnalysisJobState.SUCCEEDED

            next_ready = [row async for row in scheduler.resolve_ready_analysis_jobs(batch_size=20)]
            assert [row.id for row in next_ready] == [coordinates_job_id]

            retry_attempt_id = uuid4()
            retry_lease_token = uuid4()
            claimed_coordinates = await worker.claim_ready_analysis_job(
                ClaimReadyAnalysisJobParams(
                    resource_class=worker_models.AnalysisResourceClass.CPU,
                    attempt_id=retry_attempt_id,
                    worker_id="cpu-worker-1",
                    lease_token=retry_lease_token,
                    lease_expires_at=datetime.now(UTC) + timedelta(minutes=1),
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
                    next_attempt_at=datetime.now(UTC) - timedelta(seconds=1),
                )
            )
            assert retry_wait is not None
            assert retry_wait.state == worker_models.AnalysisJobState.RETRY_WAIT

            released = [row async for row in scheduler.release_due_analysis_retries(batch_size=20)]
            assert [row.id for row in released] == [coordinates_job_id]

            final_attempt_id = uuid4()
            final_lease_token = uuid4()
            claimed_retry = await worker.claim_ready_analysis_job(
                ClaimReadyAnalysisJobParams(
                    resource_class=worker_models.AnalysisResourceClass.CPU,
                    attempt_id=final_attempt_id,
                    worker_id="cpu-worker-1",
                    lease_token=final_lease_token,
                    lease_expires_at=datetime.now(UTC) + timedelta(minutes=1),
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
                    next_attempt_at=datetime.now(UTC) + timedelta(minutes=5),
                )
            )
            assert terminal_failure is not None
            assert terminal_failure.state == worker_models.AnalysisJobState.FAILED
            assert terminal_failure.next_attempt_at is None

            blocked = [row async for row in scheduler.block_failed_dependent_jobs(batch_size=20)]
            assert [row.id for row in blocked] == [map_job_id]

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
            await transaction.rollback()
    finally:
        await engine.dispose()
