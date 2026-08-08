-- name: ClaimReadyAnalysisJob :one
WITH candidate AS MATERIALIZED (
    SELECT
        job.*,
        definition.resource_class,
        definition.manifest,
        (
            SELECT count(*) + 1
            FROM analysis_job_attempt AS previous_attempt
            WHERE previous_attempt.job_id = job.id
        )::SMALLINT AS next_attempt_number
    FROM analysis_job AS job
    JOIN analysis_definition AS definition
        ON definition.module_id = job.module_id
        AND definition.implementation_version = job.implementation_version
    WHERE
        job.state = 'ready'
        AND job.cancel_requested_at IS NULL
        AND definition.resource_class = sqlc.arg(resource_class)
        AND (
            SELECT count(*)
            FROM analysis_job_attempt AS previous_attempt
            WHERE previous_attempt.job_id = job.id
        ) < job.max_attempts
    ORDER BY job.priority DESC, job.ready_at, job.id
    FOR UPDATE OF job SKIP LOCKED
    LIMIT 1
), updated_job AS (
    UPDATE analysis_job AS job
    SET
        state = 'running',
        started_at = COALESCE(job.started_at, now()),
        updated_at = now()
    FROM candidate
    WHERE job.id = candidate.id
    RETURNING job.*
), inserted_attempt AS (
    INSERT INTO analysis_job_attempt (
        id,
        project_id,
        job_id,
        attempt_number,
        worker_id,
        lease_token,
        lease_expires_at
    )
    SELECT
        sqlc.arg(attempt_id),
        candidate.project_id,
        candidate.id,
        candidate.next_attempt_number,
        sqlc.arg(worker_id),
        sqlc.arg(lease_token),
        now() + make_interval(secs => sqlc.arg(lease_seconds)::INT)
    FROM candidate
    JOIN updated_job ON updated_job.id = candidate.id
    RETURNING *
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
        project_id,
        job_id,
        id,
        'job.state_changed',
        'worker',
        jsonb_build_object(
            'state', 'running',
            'attempt_id', id,
            'attempt_number', attempt_number
        )
    FROM inserted_attempt
)
SELECT
    inserted_attempt.*,
    updated_job.module_id,
    updated_job.implementation_version,
    updated_job.parameters,
    updated_job.request_key,
    updated_job.cache_key,
    updated_job.source_media_id,
    candidate.resource_class,
    candidate.manifest
FROM inserted_attempt
JOIN updated_job ON updated_job.id = inserted_attempt.job_id
JOIN candidate ON candidate.id = inserted_attempt.job_id;

-- name: RenewAnalysisAttemptLease :one
WITH updated AS (
    UPDATE analysis_job_attempt AS attempt
    SET
        heartbeat_at = now(),
        lease_expires_at = now() + make_interval(secs => sqlc.arg(lease_seconds)::INT)
    WHERE
        attempt.id = sqlc.arg(attempt_id)
        AND attempt.lease_token = sqlc.arg(lease_token)
        AND attempt.state = 'running'
    RETURNING attempt.*
)
SELECT updated.*, job.cancel_requested_at
FROM updated
JOIN analysis_job AS job ON job.id = updated.job_id;

-- name: ReportAnalysisAttemptProgress :one
WITH updated_attempt AS (
    UPDATE analysis_job_attempt AS attempt
    SET
        heartbeat_at = now(),
        lease_expires_at = now() + make_interval(secs => sqlc.arg(lease_seconds)::INT),
        progress_stage = sqlc.arg(progress_stage),
        progress_completed = sqlc.narg(progress_completed),
        progress_total = sqlc.narg(progress_total),
        progress_message = sqlc.narg(progress_message),
        progress_at = now()
    WHERE
        attempt.id = sqlc.arg(attempt_id)
        AND attempt.lease_token = sqlc.arg(lease_token)
        AND attempt.state = 'running'
    RETURNING attempt.*
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
        project_id,
        job_id,
        id,
        'job.progress',
        'worker',
        jsonb_strip_nulls(
            jsonb_build_object(
                'stage', progress_stage,
                'completed', progress_completed,
                'total', progress_total,
                'message', progress_message
            )
        )
    FROM updated_attempt
)
SELECT updated_attempt.*, job.cancel_requested_at
FROM updated_attempt
JOIN analysis_job AS job ON job.id = updated_attempt.job_id;

-- name: CancelAnalysisAttempt :one
WITH eligible AS MATERIALIZED (
    SELECT attempt.id, attempt.project_id, attempt.job_id
    FROM analysis_job_attempt AS attempt
    JOIN analysis_job AS job ON job.id = attempt.job_id
    WHERE
        attempt.id = sqlc.arg(attempt_id)
        AND attempt.lease_token = sqlc.arg(lease_token)
        AND attempt.state = 'running'
        AND job.state = 'running'
        AND job.cancel_requested_at IS NOT NULL
    FOR UPDATE OF attempt, job
), finished_attempt AS (
    UPDATE analysis_job_attempt AS attempt
    SET
        state = 'canceled',
        error_kind = 'canceled',
        public_error_message = 'The analysis was canceled.',
        finished_at = now()
    FROM eligible
    WHERE attempt.id = eligible.id
    RETURNING attempt.*
), updated_job AS (
    UPDATE analysis_job AS job
    SET
        state = 'canceled',
        finished_at = now(),
        failure_kind = 'canceled',
        public_failure_message = 'The analysis was canceled.',
        diagnostic_id = NULL,
        updated_at = now()
    FROM eligible
    JOIN finished_attempt ON finished_attempt.id = eligible.id
    WHERE job.id = eligible.job_id
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
        finished_attempt.id,
        'job.state_changed',
        'worker',
        jsonb_build_object('state', updated_job.state)
    FROM updated_job
    JOIN finished_attempt ON finished_attempt.job_id = updated_job.id
)
SELECT * FROM updated_job;

-- name: CompleteAnalysisAttempt :one
WITH eligible AS MATERIALIZED (
    SELECT attempt.id, attempt.project_id, attempt.job_id
    FROM analysis_job_attempt AS attempt
    JOIN analysis_job AS job ON job.id = attempt.job_id
    WHERE
        attempt.id = sqlc.arg(attempt_id)
        AND attempt.lease_token = sqlc.arg(lease_token)
        AND attempt.state = 'running'
        AND job.state = 'running'
        AND job.cancel_requested_at IS NULL
    FOR UPDATE OF attempt, job
), finished_attempt AS (
    UPDATE analysis_job_attempt AS attempt
    SET state = 'succeeded', finished_at = now()
    FROM eligible
    WHERE attempt.id = eligible.id
    RETURNING attempt.*
), updated_job AS (
    UPDATE analysis_job AS job
    SET
        state = 'succeeded',
        winning_attempt_id = finished_attempt.id,
        finished_at = now(),
        updated_at = now()
    FROM finished_attempt
    WHERE job.id = finished_attempt.job_id
    RETURNING job.*
), result AS (
    INSERT INTO project_analysis_result (
        project_id,
        source_media_id,
        module_id,
        job_id
    )
    SELECT project_id, source_media_id, module_id, id
    FROM updated_job
    ON CONFLICT (project_id, source_media_id, module_id) DO UPDATE
    SET job_id = EXCLUDED.job_id, updated_at = now()
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
        project_id,
        id,
        winning_attempt_id,
        'job.state_changed',
        'worker',
        jsonb_build_object('state', state)
    FROM updated_job
)
SELECT * FROM updated_job;

-- name: PublishJsonAnalysisArtifact :one
WITH eligible AS MATERIALIZED (
    SELECT attempt.id, attempt.job_id
    FROM analysis_job_attempt AS attempt
    JOIN analysis_job AS job ON job.id = attempt.job_id
    WHERE
        attempt.id = sqlc.arg(attempt_id)
        AND attempt.lease_token = sqlc.arg(lease_token)
        AND attempt.state = 'running'
        AND job.state = 'running'
        AND job.cancel_requested_at IS NULL
    FOR UPDATE OF attempt, job
), artifact AS (
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
    SELECT
        sqlc.arg(artifact_id),
        eligible.id,
        'json',
        sqlc.arg(sha256_hex),
        sqlc.arg(size_bytes),
        sqlc.arg(media_type),
        sqlc.arg(json_payload)::JSONB,
        sqlc.arg(schema_id),
        sqlc.arg(schema_version)
    FROM eligible
    RETURNING *
), output AS (
    INSERT INTO analysis_job_artifact (job_id, artifact_id, output_name)
    SELECT eligible.job_id, artifact.id, sqlc.arg(output_name)
    FROM artifact
    JOIN eligible ON eligible.id = artifact.producer_attempt_id
    RETURNING job_id
)
SELECT artifact.* FROM artifact JOIN output ON TRUE;

-- name: FailAnalysisAttempt :one
WITH eligible AS MATERIALIZED (
    SELECT
        attempt.id,
        attempt.project_id,
        attempt.job_id,
        attempt.attempt_number,
        job.max_attempts
    FROM analysis_job_attempt AS attempt
    JOIN analysis_job AS job ON job.id = attempt.job_id
    WHERE
        attempt.id = sqlc.arg(attempt_id)
        AND attempt.lease_token = sqlc.arg(lease_token)
        AND attempt.state = 'running'
        AND job.state = 'running'
        AND job.cancel_requested_at IS NULL
    FOR UPDATE OF attempt, job
), finished_attempt AS (
    UPDATE analysis_job_attempt AS attempt
    SET
        state = 'failed',
        error_kind = sqlc.arg(error_kind),
        public_error_message = sqlc.arg(public_error_message),
        diagnostic_id = sqlc.narg(diagnostic_id),
        diagnostic_details = sqlc.narg(diagnostic_details),
        finished_at = now()
    FROM eligible
    WHERE attempt.id = eligible.id
    RETURNING attempt.*
), updated_job AS (
    UPDATE analysis_job AS job
    SET
        state = CASE
            WHEN sqlc.narg(retry_delay_seconds)::INT IS NOT NULL
                AND eligible.attempt_number < eligible.max_attempts
            THEN 'retry_wait'::analysis_job_state
            ELSE 'failed'::analysis_job_state
        END,
        next_attempt_at = CASE
            WHEN sqlc.narg(retry_delay_seconds)::INT IS NOT NULL
                AND eligible.attempt_number < eligible.max_attempts
            THEN now() + make_interval(secs => sqlc.narg(retry_delay_seconds)::INT)
            ELSE NULL
        END,
        finished_at = CASE
            WHEN sqlc.narg(retry_delay_seconds)::INT IS NOT NULL
                AND eligible.attempt_number < eligible.max_attempts
            THEN NULL
            ELSE now()
        END,
        failure_kind = sqlc.arg(error_kind),
        public_failure_message = sqlc.arg(public_error_message),
        diagnostic_id = sqlc.narg(diagnostic_id),
        updated_at = now()
    FROM eligible
    JOIN finished_attempt ON finished_attempt.id = eligible.id
    WHERE job.id = eligible.job_id
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
        finished_attempt.id,
        'job.error',
        'worker',
        jsonb_build_object(
            'state', updated_job.state,
            'error_kind', updated_job.failure_kind,
            'message', updated_job.public_failure_message,
            'diagnostic_id', updated_job.diagnostic_id,
            'next_attempt_at', updated_job.next_attempt_at
        )
    FROM updated_job
    JOIN finished_attempt ON finished_attempt.job_id = updated_job.id
)
SELECT * FROM updated_job;
