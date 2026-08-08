-- name: ListProjectAnalysisJobs :many
SELECT
    job.id,
    job.project_id,
    job.source_media_id,
    job.module_id,
    job.implementation_version,
    definition.display_name,
    definition.resource_class,
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
