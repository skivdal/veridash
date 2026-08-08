-- name: ListProjectAnalysisJobs :many
SELECT
    job.id,
    job.project_id,
    job.source_media_id,
    job.module_id,
    job.implementation_version,
    definition.display_name,
    definition.resource_class,
    definition.result_schema_version,
    definition.manifest,
    job.state,
    job.parameters,
    job.request_key,
    job.cache_key,
    job.priority,
    job.max_attempts,
    job.next_attempt_at,
    job.ready_at,
    job.started_at,
    job.finished_at,
    job.cancel_requested_at,
    job.failure_kind,
    job.public_failure_message,
    job.diagnostic_id,
    job.reused_from_job_id,
    job.winning_attempt_id,
    job.created_at,
    job.updated_at
FROM analysis_job AS job
JOIN project ON project.id = job.project_id
JOIN analysis_definition AS definition
    ON definition.module_id = job.module_id
    AND definition.implementation_version = job.implementation_version
WHERE job.project_id = sqlc.arg(project_id) AND project.user_id = sqlc.arg(user_id)
ORDER BY job.created_at, job.id;

-- name: ListProjectAnalysisAttempts :many
SELECT
    attempt.id,
    attempt.project_id,
    attempt.job_id,
    attempt.attempt_number,
    attempt.state,
    attempt.worker_id,
    attempt.lease_expires_at,
    attempt.heartbeat_at,
    attempt.progress_stage,
    attempt.progress_completed,
    attempt.progress_total,
    attempt.progress_message,
    attempt.progress_at,
    attempt.error_kind,
    attempt.public_error_message,
    attempt.diagnostic_id,
    attempt.started_at,
    attempt.finished_at
FROM analysis_job_attempt AS attempt
JOIN project ON project.id = attempt.project_id
WHERE attempt.project_id = sqlc.arg(project_id) AND project.user_id = sqlc.arg(user_id)
ORDER BY attempt.job_id, attempt.attempt_number;

-- name: GetAnalysisJob :one
SELECT
    job.id,
    job.project_id,
    job.source_media_id,
    job.module_id,
    job.implementation_version,
    definition.display_name,
    definition.resource_class,
    definition.result_schema_version,
    definition.manifest,
    job.state,
    job.parameters,
    job.request_key,
    job.cache_key,
    job.priority,
    job.max_attempts,
    job.next_attempt_at,
    job.ready_at,
    job.started_at,
    job.finished_at,
    job.cancel_requested_at,
    job.failure_kind,
    job.public_failure_message,
    job.diagnostic_id,
    job.reused_from_job_id,
    job.winning_attempt_id,
    job.created_at,
    job.updated_at
FROM analysis_job AS job
JOIN project ON project.id = job.project_id
JOIN analysis_definition AS definition
    ON definition.module_id = job.module_id
    AND definition.implementation_version = job.implementation_version
WHERE job.id = sqlc.arg(job_id) AND project.user_id = sqlc.arg(user_id)
LIMIT 1;

-- name: RequestProjectAnalysisJobCancellation :one
WITH target AS MATERIALIZED (
    SELECT job.*
    FROM analysis_job AS job
    JOIN project ON project.id = job.project_id
    WHERE
        job.id = sqlc.arg(job_id)
        AND job.project_id = sqlc.arg(project_id)
        AND project.user_id = sqlc.arg(user_id)
        AND job.state IN (
            'waiting_for_dependencies',
            'ready',
            'running',
            'retry_wait',
            'canceled'
        )
    FOR UPDATE OF job
), updated AS (
    UPDATE analysis_job AS job
    SET
        cancel_requested_at = COALESCE(job.cancel_requested_at, now()),
        state = CASE
            WHEN target.state = 'running' THEN 'running'::analysis_job_state
            ELSE 'canceled'::analysis_job_state
        END,
        next_attempt_at = NULL,
        finished_at = CASE
            WHEN target.state = 'running' THEN NULL
            ELSE COALESCE(job.finished_at, now())
        END,
        failure_kind = CASE
            WHEN target.state = 'running' THEN NULL
            ELSE 'canceled'::analysis_error_kind
        END,
        public_failure_message = CASE
            WHEN target.state = 'running' THEN NULL
            ELSE 'The analysis was canceled.'
        END,
        diagnostic_id = NULL,
        updated_at = CASE
            WHEN target.cancel_requested_at IS NULL THEN now()
            ELSE job.updated_at
        END
    FROM target
    WHERE job.id = target.id
    RETURNING job.*
), event AS (
    INSERT INTO project_event (project_id, job_id, event_type, source, payload)
    SELECT
        updated.project_id,
        updated.id,
        CASE
            WHEN updated.state = 'running' THEN 'job.cancel_requested'
            ELSE 'job.state_changed'
        END,
        'user',
        jsonb_build_object('state', updated.state)
    FROM updated
    JOIN target ON target.id = updated.id
    WHERE target.cancel_requested_at IS NULL
)
SELECT * FROM updated;

-- name: RequestProjectAnalysisJobRetry :one
WITH RECURSIVE target AS MATERIALIZED (
    SELECT job.*
    FROM analysis_job AS job
    JOIN project ON project.id = job.project_id
    WHERE
        job.id = sqlc.arg(job_id)
        AND job.project_id = sqlc.arg(project_id)
        AND project.user_id = sqlc.arg(user_id)
        AND job.state IN ('failed', 'blocked', 'canceled', 'waiting_for_dependencies')
        AND (
            job.state = 'waiting_for_dependencies'
            OR (
                SELECT count(*)
                FROM analysis_job_attempt AS attempt
                WHERE attempt.job_id = job.id
            ) < 100
        )
    FOR UPDATE OF job
), retried AS (
    UPDATE analysis_job AS job
    SET
        state = 'waiting_for_dependencies',
        max_attempts = CASE
            WHEN target.state = 'waiting_for_dependencies' THEN job.max_attempts
            ELSE GREATEST(
                job.max_attempts,
                (
                    SELECT count(*) + 1
                    FROM analysis_job_attempt AS attempt
                    WHERE attempt.job_id = target.id
                )::SMALLINT
            )
        END,
        next_attempt_at = NULL,
        ready_at = NULL,
        finished_at = NULL,
        cancel_requested_at = NULL,
        failure_kind = NULL,
        public_failure_message = NULL,
        diagnostic_id = NULL,
        updated_at = CASE
            WHEN target.state = 'waiting_for_dependencies' THEN job.updated_at
            ELSE now()
        END
    FROM target
    WHERE job.id = target.id
    RETURNING job.*
), descendant_ids AS (
    SELECT dependency.job_id
    FROM analysis_job_dependency AS dependency
    JOIN target ON target.id = dependency.depends_on_job_id
    UNION
    SELECT dependency.job_id
    FROM analysis_job_dependency AS dependency
    JOIN descendant_ids ON descendant_ids.job_id = dependency.depends_on_job_id
), unblocked AS (
    UPDATE analysis_job AS job
    SET
        state = 'waiting_for_dependencies',
        finished_at = NULL,
        failure_kind = NULL,
        public_failure_message = NULL,
        diagnostic_id = NULL,
        updated_at = now()
    FROM descendant_ids
    WHERE
        job.id = descendant_ids.job_id
        AND job.state = 'blocked'
        AND job.failure_kind = 'dependency_failed'
    RETURNING job.*
), target_event AS (
    INSERT INTO project_event (project_id, job_id, event_type, source, payload)
    SELECT
        retried.project_id,
        retried.id,
        'job.retry_requested',
        'user',
        jsonb_build_object('state', retried.state)
    FROM retried
    JOIN target ON target.id = retried.id
    WHERE target.state <> 'waiting_for_dependencies'
), descendant_events AS (
    INSERT INTO project_event (project_id, job_id, event_type, source, payload)
    SELECT
        project_id,
        id,
        'job.state_changed',
        'user',
        jsonb_build_object('state', state, 'reason', 'dependency_retry')
    FROM unblocked
)
SELECT * FROM retried;

-- name: ListAnalysisJobArtifacts :many
SELECT
    artifact.id,
    link.output_name,
    artifact.kind,
    artifact.sha256_hex,
    artifact.size_bytes,
    artifact.media_type,
    artifact.json_payload,
    artifact.schema_id,
    artifact.schema_version,
    artifact.created_at
FROM analysis_job_artifact AS link
JOIN analysis_artifact AS artifact ON artifact.id = link.artifact_id
JOIN analysis_job AS job ON job.id = link.job_id
JOIN project ON project.id = job.project_id
WHERE link.job_id = sqlc.arg(job_id) AND project.user_id = sqlc.arg(user_id)
ORDER BY link.output_name;

-- name: GetProjectAnalysisBlobArtifact :one
SELECT
    artifact.id,
    link.output_name,
    artifact.sha256_hex,
    artifact.size_bytes,
    artifact.media_type,
    artifact.blob_key
FROM analysis_job_artifact AS link
JOIN analysis_artifact AS artifact ON artifact.id = link.artifact_id
JOIN analysis_job AS job ON job.id = link.job_id
JOIN project ON project.id = job.project_id
WHERE
    job.project_id = sqlc.arg(project_id)
    AND link.job_id = sqlc.arg(job_id)
    AND artifact.id = sqlc.arg(artifact_id)
    AND artifact.kind = 'blob'
    AND project.user_id = sqlc.arg(user_id)
LIMIT 1;

-- name: ListProjectEventsAfter :many
SELECT
    event.id,
    event.project_id,
    event.job_id,
    event.attempt_id,
    event.event_type,
    event.source,
    event.payload_version,
    event.payload,
    event.created_at
FROM project_event AS event
JOIN project ON project.id = event.project_id
WHERE
    event.project_id = sqlc.arg(project_id)
    AND project.user_id = sqlc.arg(user_id)
    AND event.id > sqlc.arg(after_event_id)
ORDER BY event.id
LIMIT sqlc.arg(batch_size);

-- name: GetLatestProjectEventId :one
SELECT COALESCE(max(event.id), 0)::BIGINT AS latest_event_id
FROM project_event AS event
JOIN project ON project.id = event.project_id
WHERE event.project_id = sqlc.arg(project_id) AND project.user_id = sqlc.arg(user_id);

-- name: RegisterAnalysisDefinition :one
WITH inserted AS (
    INSERT INTO analysis_definition (
        module_id,
        implementation_version,
        display_name,
        result_schema_version,
        resource_class,
        automatic,
        manifest_hash,
        manifest
    )
    VALUES (
        sqlc.arg(module_id),
        sqlc.arg(implementation_version),
        sqlc.arg(display_name),
        sqlc.arg(result_schema_version),
        sqlc.arg(resource_class),
        sqlc.arg(automatic),
        sqlc.arg(manifest_hash),
        sqlc.arg(manifest)
    )
    ON CONFLICT (module_id, implementation_version) DO NOTHING
    RETURNING *
)
SELECT * FROM inserted
UNION ALL
SELECT * FROM analysis_definition
WHERE
    module_id = sqlc.arg(module_id)
    AND implementation_version = sqlc.arg(implementation_version)
LIMIT 1;

-- name: CreateAutomaticAnalysisJob :one
WITH inserted AS (
    INSERT INTO analysis_job (
        id,
        project_id,
        source_media_id,
        module_id,
        implementation_version,
        parameters,
        request_key,
        cache_key,
        priority,
        max_attempts
    )
    VALUES (
        sqlc.arg(id),
        sqlc.arg(project_id),
        sqlc.arg(source_media_id),
        sqlc.arg(module_id),
        sqlc.arg(implementation_version),
        sqlc.arg(parameters),
        sqlc.arg(request_key),
        sqlc.narg(cache_key),
        sqlc.arg(priority),
        sqlc.arg(max_attempts)
    )
    ON CONFLICT (project_id, source_media_id, module_id, request_key) DO NOTHING
    RETURNING *
), selected AS (
    SELECT * FROM inserted
    UNION ALL
    SELECT * FROM analysis_job
    WHERE
        project_id = sqlc.arg(project_id)
        AND source_media_id = sqlc.arg(source_media_id)
        AND module_id = sqlc.arg(module_id)
        AND request_key = sqlc.arg(request_key)
    LIMIT 1
), event AS (
    INSERT INTO project_event (project_id, job_id, event_type, source, payload)
    SELECT
        project_id,
        id,
        'job.created',
        'api',
        jsonb_build_object('state', state, 'module_id', module_id)
    FROM inserted
)
SELECT * FROM selected;

-- name: AddAutomaticAnalysisDependency :exec
INSERT INTO analysis_job_dependency (project_id, job_id, depends_on_job_id)
VALUES (sqlc.arg(project_id), sqlc.arg(job_id), sqlc.arg(depends_on_job_id))
ON CONFLICT (job_id, depends_on_job_id) DO NOTHING;

-- name: AppendMediaUploadedEvent :exec
INSERT INTO project_event (project_id, event_type, source, payload)
VALUES (
    sqlc.arg(project_id),
    'media.uploaded',
    'api',
    jsonb_build_object('media_id', sqlc.arg(media_id)::UUID)
);
