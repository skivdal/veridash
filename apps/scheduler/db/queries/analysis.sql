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

-- name: ListKnownCacheResolvableJobs :many
SELECT job.id, job.cache_key
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
LIMIT sqlc.arg(batch_size);

-- name: ListDependentCacheInputs :many
WITH candidates AS MATERIALIZED (
    SELECT job.id
    FROM analysis_job AS job
    WHERE
        job.state = 'waiting_for_dependencies'
        AND job.cache_key IS NULL
        AND EXISTS (
            SELECT 1 FROM analysis_job_dependency AS dependency
            WHERE dependency.job_id = job.id
        )
        AND NOT EXISTS (
            SELECT 1
            FROM analysis_job_dependency AS dependency
            JOIN analysis_job AS upstream ON upstream.id = dependency.depends_on_job_id
            WHERE dependency.job_id = job.id AND upstream.state <> 'succeeded'
        )
        AND NOT EXISTS (
            SELECT 1
            FROM analysis_job_dependency AS dependency
            WHERE
                dependency.job_id = job.id
                AND NOT EXISTS (
                    SELECT 1 FROM analysis_job_artifact AS output
                    WHERE output.job_id = dependency.depends_on_job_id
                )
        )
    ORDER BY job.priority DESC, job.created_at, job.id
    FOR UPDATE OF job SKIP LOCKED
    LIMIT sqlc.arg(batch_size)
)
SELECT
    job.id AS job_id,
    job.project_id,
    job.source_media_id,
    source_media.sha256_hex AS source_sha256,
    job.module_id,
    job.implementation_version,
    job.parameters,
    definition.manifest,
    upstream.module_id AS dependency_module_id,
    upstream_definition.manifest AS dependency_manifest,
    output.output_name,
    artifact.sha256_hex AS artifact_sha256,
    artifact.kind AS artifact_kind,
    artifact.media_type AS artifact_media_type,
    artifact.schema_id AS artifact_schema_id,
    artifact.schema_version AS artifact_schema_version
FROM candidates
JOIN analysis_job AS job ON job.id = candidates.id
JOIN source_media ON source_media.id = job.source_media_id
JOIN analysis_definition AS definition
    ON definition.module_id = job.module_id
    AND definition.implementation_version = job.implementation_version
JOIN analysis_job_dependency AS dependency ON dependency.job_id = job.id
JOIN analysis_job AS upstream ON upstream.id = dependency.depends_on_job_id
JOIN analysis_definition AS upstream_definition
    ON upstream_definition.module_id = upstream.module_id
    AND upstream_definition.implementation_version = upstream.implementation_version
JOIN analysis_job_artifact AS output ON output.job_id = upstream.id
JOIN analysis_artifact AS artifact ON artifact.id = output.artifact_id
ORDER BY job.id, upstream.module_id, output.output_name;

-- name: ResolveAnalysisJobCache :one
WITH target AS MATERIALIZED (
    SELECT job.*
    FROM analysis_job AS job
    WHERE
        job.id = sqlc.arg(job_id)
        AND job.state = 'waiting_for_dependencies'
        AND (
            job.cache_key IS NULL
            OR job.cache_key = sqlc.arg(cache_key)
        )
    FOR UPDATE OF job
), reusable AS MATERIALIZED (
    SELECT cached.id
    FROM analysis_job AS cached
    JOIN target
        ON target.module_id = cached.module_id
        AND target.implementation_version = cached.implementation_version
    WHERE
        cached.state = 'succeeded'
        AND cached.cache_key = sqlc.arg(cache_key)
        AND cached.id <> target.id
    ORDER BY cached.finished_at, cached.id
    LIMIT 1
), updated AS (
    UPDATE analysis_job AS job
    SET
        cache_key = sqlc.arg(cache_key),
        state = CASE
            WHEN reusable.id IS NULL THEN 'ready'::analysis_job_state
            ELSE 'succeeded'::analysis_job_state
        END,
        ready_at = CASE WHEN reusable.id IS NULL THEN now() ELSE NULL END,
        finished_at = CASE WHEN reusable.id IS NULL THEN NULL ELSE now() END,
        reused_from_job_id = reusable.id,
        updated_at = now()
    FROM target
    LEFT JOIN reusable ON TRUE
    WHERE job.id = target.id
    RETURNING job.*
), copied_outputs AS (
    INSERT INTO analysis_job_artifact (job_id, artifact_id, output_name)
    SELECT updated.id, output.artifact_id, output.output_name
    FROM updated
    JOIN reusable ON reusable.id = updated.reused_from_job_id
    JOIN analysis_job_artifact AS output ON output.job_id = reusable.id
    ON CONFLICT (job_id, output_name) DO NOTHING
), result AS (
    INSERT INTO project_analysis_result (
        project_id,
        source_media_id,
        module_id,
        job_id
    )
    SELECT project_id, source_media_id, module_id, id
    FROM updated
    WHERE state = 'succeeded'
    ON CONFLICT (project_id, source_media_id, module_id) DO UPDATE
    SET job_id = EXCLUDED.job_id, updated_at = now()
), event AS (
    INSERT INTO project_event (project_id, job_id, event_type, source, payload)
    SELECT
        project_id,
        id,
        'job.state_changed',
        'scheduler',
        jsonb_build_object(
            'state', state,
            'reused', reused_from_job_id IS NOT NULL
        )
    FROM updated
)
SELECT * FROM updated;

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

-- name: RecoverExpiredAnalysisAttempts :many
WITH candidates AS MATERIALIZED (
    SELECT
        attempt.id,
        attempt.project_id,
        attempt.job_id,
        attempt.attempt_number,
        job.max_attempts,
        job.cancel_requested_at
    FROM analysis_job_attempt AS attempt
    JOIN analysis_job AS job ON job.id = attempt.job_id
    WHERE
        attempt.state = 'running'
        AND attempt.lease_expires_at < now()
        AND job.state = 'running'
    ORDER BY attempt.lease_expires_at, attempt.id
    FOR UPDATE OF attempt, job SKIP LOCKED
    LIMIT sqlc.arg(batch_size)
), lost_attempt AS (
    UPDATE analysis_job_attempt AS attempt
    SET
        state = CASE
            WHEN candidates.cancel_requested_at IS NOT NULL
            THEN 'canceled'::analysis_attempt_state
            ELSE 'lost'::analysis_attempt_state
        END,
        error_kind = CASE
            WHEN candidates.cancel_requested_at IS NOT NULL
            THEN 'canceled'::analysis_error_kind
            ELSE 'worker_lost'::analysis_error_kind
        END,
        public_error_message = CASE
            WHEN candidates.cancel_requested_at IS NOT NULL
            THEN 'The analysis was canceled.'
            ELSE 'The analysis worker stopped responding.'
        END,
        finished_at = now()
    FROM candidates
    WHERE attempt.id = candidates.id
    RETURNING attempt.*
), updated_job AS (
    UPDATE analysis_job AS job
    SET
        state = CASE
            WHEN candidates.cancel_requested_at IS NOT NULL
            THEN 'canceled'::analysis_job_state
            WHEN candidates.attempt_number < candidates.max_attempts
            THEN 'retry_wait'::analysis_job_state
            ELSE 'failed'::analysis_job_state
        END,
        next_attempt_at = CASE
            WHEN candidates.cancel_requested_at IS NULL
                AND candidates.attempt_number < candidates.max_attempts
            THEN now() + make_interval(secs => sqlc.arg(retry_delay_seconds)::INT)
            ELSE NULL
        END,
        finished_at = CASE
            WHEN candidates.cancel_requested_at IS NULL
                AND candidates.attempt_number < candidates.max_attempts
            THEN NULL
            ELSE now()
        END,
        failure_kind = CASE
            WHEN candidates.cancel_requested_at IS NOT NULL
            THEN 'canceled'::analysis_error_kind
            ELSE 'worker_lost'::analysis_error_kind
        END,
        public_failure_message = CASE
            WHEN candidates.cancel_requested_at IS NOT NULL
            THEN 'The analysis was canceled.'
            ELSE 'The analysis worker stopped responding.'
        END,
        updated_at = now()
    FROM candidates
    JOIN lost_attempt ON lost_attempt.id = candidates.id
    WHERE job.id = candidates.job_id
    RETURNING job.*
), event AS (
    INSERT INTO project_event (
        project_id,
        job_id,
        attempt_id,
        event_type,
        source,
        payload
    )
    SELECT
        updated_job.project_id,
        updated_job.id,
        lost_attempt.id,
        CASE
            WHEN updated_job.state = 'canceled' THEN 'job.state_changed'
            ELSE 'job.error'
        END,
        'scheduler',
        jsonb_build_object(
            'state', updated_job.state,
            'error_kind', updated_job.failure_kind,
            'message', updated_job.public_failure_message,
            'next_attempt_at', updated_job.next_attempt_at
        )
    FROM updated_job
    JOIN lost_attempt ON lost_attempt.job_id = updated_job.id
)
SELECT * FROM updated_job ORDER BY updated_at, id;
