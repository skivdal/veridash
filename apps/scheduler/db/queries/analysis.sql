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

-- name: CreateAnalysisJob :one
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
        sqlc.arg(cache_key),
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
        'scheduler',
        jsonb_build_object('state', state, 'module_id', module_id)
    FROM inserted
)
SELECT * FROM selected;

-- name: AddAnalysisJobDependency :exec
INSERT INTO analysis_job_dependency (project_id, job_id, depends_on_job_id)
VALUES (sqlc.arg(project_id), sqlc.arg(job_id), sqlc.arg(depends_on_job_id))
ON CONFLICT (job_id, depends_on_job_id) DO NOTHING;

-- name: ResolveReadyAnalysisJobs :many
WITH candidates AS MATERIALIZED (
    SELECT job.id
    FROM analysis_job AS job
    WHERE
        job.state = 'waiting_for_dependencies'
        AND job.cache_key IS NOT NULL
        AND NOT EXISTS (
            SELECT 1
            FROM analysis_job_dependency AS dependency
            JOIN analysis_job AS upstream ON upstream.id = dependency.depends_on_job_id
            WHERE dependency.job_id = job.id AND upstream.state <> 'succeeded'
        )
    ORDER BY job.priority DESC, job.created_at, job.id
    FOR UPDATE OF job SKIP LOCKED
    LIMIT sqlc.arg(batch_size)
), updated AS (
    UPDATE analysis_job AS job
    SET
        state = 'ready',
        ready_at = now(),
        updated_at = now()
    FROM candidates
    WHERE job.id = candidates.id
    RETURNING job.*
), event AS (
    INSERT INTO project_event (project_id, job_id, event_type, source, payload)
    SELECT
        project_id,
        id,
        'job.state_changed',
        'scheduler',
        jsonb_build_object('state', state)
    FROM updated
)
SELECT * FROM updated ORDER BY priority DESC, created_at, id;

-- name: BlockFailedDependentJobs :many
WITH candidates AS MATERIALIZED (
    SELECT job.id
    FROM analysis_job AS job
    WHERE
        job.state = 'waiting_for_dependencies'
        AND EXISTS (
            SELECT 1
            FROM analysis_job_dependency AS dependency
            JOIN analysis_job AS upstream ON upstream.id = dependency.depends_on_job_id
            WHERE
                dependency.job_id = job.id
                AND upstream.state IN ('failed', 'blocked', 'canceled')
        )
    ORDER BY job.created_at, job.id
    FOR UPDATE OF job SKIP LOCKED
    LIMIT sqlc.arg(batch_size)
), updated AS (
    UPDATE analysis_job AS job
    SET
        state = 'blocked',
        finished_at = now(),
        failure_kind = 'dependency_failed',
        public_failure_message = 'A required analysis did not complete successfully.',
        updated_at = now()
    FROM candidates
    WHERE job.id = candidates.id
    RETURNING job.*
), event AS (
    INSERT INTO project_event (project_id, job_id, event_type, source, payload)
    SELECT
        project_id,
        id,
        'job.state_changed',
        'scheduler',
        jsonb_build_object(
            'state', state,
            'error_kind', failure_kind,
            'message', public_failure_message
        )
    FROM updated
)
SELECT * FROM updated ORDER BY created_at, id;

-- name: ReleaseDueAnalysisRetries :many
WITH candidates AS MATERIALIZED (
    SELECT job.id
    FROM analysis_job AS job
    WHERE job.state = 'retry_wait' AND job.next_attempt_at <= now()
    ORDER BY job.next_attempt_at, job.id
    FOR UPDATE OF job SKIP LOCKED
    LIMIT sqlc.arg(batch_size)
), updated AS (
    UPDATE analysis_job AS job
    SET
        state = 'ready',
        next_attempt_at = NULL,
        ready_at = now(),
        failure_kind = NULL,
        public_failure_message = NULL,
        diagnostic_id = NULL,
        updated_at = now()
    FROM candidates
    WHERE job.id = candidates.id
    RETURNING job.*
), event AS (
    INSERT INTO project_event (project_id, job_id, event_type, source, payload)
    SELECT
        project_id,
        id,
        'job.state_changed',
        'scheduler',
        jsonb_build_object('state', state)
    FROM updated
)
SELECT * FROM updated ORDER BY priority DESC, ready_at, id;
