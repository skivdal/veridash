-- migrate:up

CREATE TYPE analysis_resource_class AS ENUM ('cpu', 'gpu', 'translation');
CREATE TYPE analysis_job_state AS ENUM (
    'waiting_for_dependencies',
    'ready',
    'running',
    'retry_wait',
    'succeeded',
    'failed',
    'blocked',
    'canceled'
);
CREATE TYPE analysis_attempt_state AS ENUM (
    'running',
    'succeeded',
    'failed',
    'canceled',
    'lost'
);
CREATE TYPE analysis_error_kind AS ENUM (
    'invalid_input',
    'dependency_failed',
    'transient_infrastructure',
    'resource_exhausted',
    'worker_lost',
    'stalled',
    'rate_limited',
    'provider_unavailable',
    'canceled',
    'internal_bug'
);
CREATE TYPE analysis_artifact_kind AS ENUM ('blob', 'json');
CREATE TYPE project_event_source AS ENUM ('api', 'scheduler', 'worker', 'user', 'system');

ALTER TABLE source_media
ADD CONSTRAINT source_media_project_identity UNIQUE (project_id, id);

CREATE TABLE analysis_definition (
    module_id TEXT NOT NULL,
    implementation_version TEXT NOT NULL,
    display_name TEXT NOT NULL,
    result_schema_version INTEGER NOT NULL,
    resource_class analysis_resource_class NOT NULL,
    automatic BOOLEAN NOT NULL,
    manifest_hash TEXT NOT NULL,
    manifest JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (module_id, implementation_version),
    CONSTRAINT analysis_definition_module_id_shape CHECK (
        module_id ~ '^[a-z][a-z0-9_]*$' AND char_length(module_id) <= 100
    ),
    CONSTRAINT analysis_definition_version_not_blank CHECK (
        char_length(btrim(implementation_version)) BETWEEN 1 AND 100
    ),
    CONSTRAINT analysis_definition_display_name_not_blank CHECK (
        char_length(btrim(display_name)) BETWEEN 1 AND 200
    ),
    CONSTRAINT analysis_definition_schema_version_positive CHECK (
        result_schema_version > 0
    ),
    CONSTRAINT analysis_definition_manifest_hash_shape CHECK (
        manifest_hash ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT analysis_definition_manifest_object CHECK (
        jsonb_typeof(manifest) = 'object'
    )
);

CREATE TABLE analysis_job (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES project(id) ON DELETE RESTRICT,
    source_media_id UUID NOT NULL,
    module_id TEXT NOT NULL,
    implementation_version TEXT NOT NULL,
    state analysis_job_state NOT NULL DEFAULT 'waiting_for_dependencies',
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    cache_key TEXT NOT NULL,
    priority SMALLINT NOT NULL DEFAULT 0,
    max_attempts SMALLINT NOT NULL DEFAULT 3,
    next_attempt_at TIMESTAMPTZ,
    ready_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    cancel_requested_at TIMESTAMPTZ,
    failure_kind analysis_error_kind,
    public_failure_message TEXT,
    diagnostic_id UUID,
    reused_from_job_id UUID REFERENCES analysis_job(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, id),
    UNIQUE (project_id, id, module_id, source_media_id),
    UNIQUE (project_id, source_media_id, module_id, cache_key),
    FOREIGN KEY (project_id, source_media_id)
        REFERENCES source_media(project_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (module_id, implementation_version)
        REFERENCES analysis_definition(module_id, implementation_version) ON DELETE RESTRICT,
    CONSTRAINT analysis_job_parameters_object CHECK (jsonb_typeof(parameters) = 'object'),
    CONSTRAINT analysis_job_cache_key_shape CHECK (cache_key ~ '^[0-9a-f]{64}$'),
    CONSTRAINT analysis_job_attempt_limit CHECK (max_attempts BETWEEN 1 AND 100),
    CONSTRAINT analysis_job_retry_time_consistent CHECK (
        (state = 'retry_wait') = (next_attempt_at IS NOT NULL)
    ),
    CONSTRAINT analysis_job_finished_consistent CHECK (
        (state IN ('succeeded', 'failed', 'blocked', 'canceled')) = (finished_at IS NOT NULL)
    ),
    CONSTRAINT analysis_job_failure_consistent CHECK (
        (
            state IN ('retry_wait', 'failed', 'blocked', 'canceled')
            AND failure_kind IS NOT NULL
            AND public_failure_message IS NOT NULL
        )
        OR (
            state NOT IN ('retry_wait', 'failed', 'blocked', 'canceled')
            AND failure_kind IS NULL
            AND public_failure_message IS NULL
            AND diagnostic_id IS NULL
        )
    ),
    CONSTRAINT analysis_job_failure_message_length CHECK (
        public_failure_message IS NULL OR char_length(public_failure_message) <= 1000
    ),
    CONSTRAINT analysis_job_terminal_error_kind CHECK (
        (state <> 'blocked' OR failure_kind = 'dependency_failed')
        AND (state <> 'canceled' OR failure_kind = 'canceled')
    ),
    CONSTRAINT analysis_job_reuse_state CHECK (
        reused_from_job_id IS NULL OR state = 'succeeded'
    )
);

CREATE INDEX analysis_job_project_created_idx
ON analysis_job (project_id, created_at, id);

CREATE INDEX analysis_job_schedulable_idx
ON analysis_job (state, priority DESC, ready_at, id)
WHERE state IN ('ready', 'retry_wait', 'running');

CREATE INDEX analysis_job_cache_lookup_idx
ON analysis_job (cache_key, finished_at DESC)
WHERE state = 'succeeded';

CREATE TABLE analysis_job_dependency (
    project_id UUID NOT NULL,
    job_id UUID NOT NULL,
    depends_on_job_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (job_id, depends_on_job_id),
    FOREIGN KEY (project_id, job_id)
        REFERENCES analysis_job(project_id, id) ON DELETE CASCADE,
    FOREIGN KEY (project_id, depends_on_job_id)
        REFERENCES analysis_job(project_id, id) ON DELETE RESTRICT,
    CONSTRAINT analysis_job_dependency_not_self CHECK (job_id <> depends_on_job_id)
);

CREATE INDEX analysis_job_dependency_upstream_idx
ON analysis_job_dependency (depends_on_job_id, job_id);

CREATE TABLE analysis_job_attempt (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL,
    job_id UUID NOT NULL,
    attempt_number SMALLINT NOT NULL,
    state analysis_attempt_state NOT NULL DEFAULT 'running',
    worker_id TEXT NOT NULL,
    lease_token UUID NOT NULL UNIQUE,
    lease_expires_at TIMESTAMPTZ NOT NULL,
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    progress_stage TEXT,
    progress_completed BIGINT,
    progress_total BIGINT,
    progress_message TEXT,
    progress_at TIMESTAMPTZ,
    error_kind analysis_error_kind,
    public_error_message TEXT,
    diagnostic_id UUID,
    diagnostic_details JSONB,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    UNIQUE (job_id, attempt_number),
    UNIQUE (project_id, job_id, id),
    FOREIGN KEY (project_id, job_id)
        REFERENCES analysis_job(project_id, id) ON DELETE CASCADE,
    CONSTRAINT analysis_job_attempt_number_positive CHECK (attempt_number > 0),
    CONSTRAINT analysis_job_attempt_worker_id_not_blank CHECK (
        char_length(btrim(worker_id)) BETWEEN 1 AND 200
    ),
    CONSTRAINT analysis_job_attempt_finished_consistent CHECK (
        (state <> 'running') = (finished_at IS NOT NULL)
    ),
    CONSTRAINT analysis_job_attempt_error_consistent CHECK (
        (
            state IN ('failed', 'lost', 'canceled')
            AND error_kind IS NOT NULL
            AND public_error_message IS NOT NULL
        )
        OR (
            state NOT IN ('failed', 'lost', 'canceled')
            AND error_kind IS NULL
            AND public_error_message IS NULL
            AND diagnostic_id IS NULL
            AND diagnostic_details IS NULL
        )
    ),
    CONSTRAINT analysis_job_attempt_error_message_length CHECK (
        public_error_message IS NULL OR char_length(public_error_message) <= 1000
    ),
    CONSTRAINT analysis_job_attempt_canceled_kind CHECK (
        state <> 'canceled' OR error_kind = 'canceled'
    ),
    CONSTRAINT analysis_job_attempt_progress_nonnegative CHECK (
        (progress_completed IS NULL OR progress_completed >= 0)
        AND (progress_total IS NULL OR progress_total > 0)
        AND (
            progress_completed IS NULL
            OR progress_total IS NULL
            OR progress_completed <= progress_total
        )
    ),
    CONSTRAINT analysis_job_attempt_progress_stage_length CHECK (
        progress_stage IS NULL OR char_length(progress_stage) <= 100
    ),
    CONSTRAINT analysis_job_attempt_progress_message_length CHECK (
        progress_message IS NULL OR char_length(progress_message) <= 1000
    ),
    CONSTRAINT analysis_job_attempt_diagnostic_object CHECK (
        diagnostic_details IS NULL OR jsonb_typeof(diagnostic_details) = 'object'
    )
);

CREATE UNIQUE INDEX analysis_job_attempt_one_running_idx
ON analysis_job_attempt (job_id)
WHERE state = 'running';

CREATE INDEX analysis_job_attempt_expired_lease_idx
ON analysis_job_attempt (lease_expires_at, id)
WHERE state = 'running';

ALTER TABLE analysis_job ADD COLUMN winning_attempt_id UUID;
ALTER TABLE analysis_job
ADD CONSTRAINT analysis_job_winning_attempt_fk
FOREIGN KEY (project_id, id, winning_attempt_id)
REFERENCES analysis_job_attempt(project_id, job_id, id) ON DELETE RESTRICT;
ALTER TABLE analysis_job
ADD CONSTRAINT analysis_job_success_consistent CHECK (
    (
        state = 'succeeded'
        AND (
            (winning_attempt_id IS NOT NULL AND reused_from_job_id IS NULL)
            OR (winning_attempt_id IS NULL AND reused_from_job_id IS NOT NULL)
        )
    )
    OR (
        state <> 'succeeded'
        AND winning_attempt_id IS NULL
        AND reused_from_job_id IS NULL
    )
);

CREATE TABLE analysis_artifact (
    id UUID PRIMARY KEY,
    producer_attempt_id UUID NOT NULL REFERENCES analysis_job_attempt(id) ON DELETE RESTRICT,
    kind analysis_artifact_kind NOT NULL,
    sha256_hex TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    media_type TEXT NOT NULL,
    blob_key TEXT,
    json_payload JSONB,
    schema_id TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT analysis_artifact_sha256_shape CHECK (sha256_hex ~ '^[0-9a-f]{64}$'),
    CONSTRAINT analysis_artifact_size_nonnegative CHECK (size_bytes >= 0),
    CONSTRAINT analysis_artifact_media_type_not_blank CHECK (
        char_length(btrim(media_type)) BETWEEN 1 AND 255
    ),
    CONSTRAINT analysis_artifact_schema_id_shape CHECK (
        schema_id ~ '^[a-z][a-z0-9_.-]*$' AND char_length(schema_id) <= 200
    ),
    CONSTRAINT analysis_artifact_schema_version_positive CHECK (schema_version > 0),
    CONSTRAINT analysis_artifact_representation_consistent CHECK (
        (kind = 'blob' AND blob_key IS NOT NULL AND json_payload IS NULL)
        OR (kind = 'json' AND blob_key IS NULL AND json_payload IS NOT NULL)
    )
);

CREATE INDEX analysis_artifact_hash_idx
ON analysis_artifact (sha256_hex, schema_id, schema_version);

CREATE TABLE analysis_job_artifact (
    job_id UUID NOT NULL REFERENCES analysis_job(id) ON DELETE CASCADE,
    artifact_id UUID NOT NULL REFERENCES analysis_artifact(id) ON DELETE RESTRICT,
    output_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (job_id, output_name),
    UNIQUE (job_id, artifact_id),
    CONSTRAINT analysis_job_artifact_output_name_shape CHECK (
        output_name ~ '^[a-z][a-z0-9_]*$' AND char_length(output_name) <= 100
    )
);

CREATE TABLE project_analysis_result (
    project_id UUID NOT NULL,
    source_media_id UUID NOT NULL,
    module_id TEXT NOT NULL,
    job_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, source_media_id, module_id),
    FOREIGN KEY (project_id, source_media_id)
        REFERENCES source_media(project_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (project_id, job_id, module_id, source_media_id)
        REFERENCES analysis_job(project_id, id, module_id, source_media_id)
        ON DELETE RESTRICT,
    CONSTRAINT project_analysis_result_module_id_shape CHECK (
        module_id ~ '^[a-z][a-z0-9_]*$' AND char_length(module_id) <= 100
    )
);

CREATE TABLE project_event (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES project(id) ON DELETE RESTRICT,
    job_id UUID,
    attempt_id UUID,
    event_type TEXT NOT NULL,
    source project_event_source NOT NULL,
    payload_version INTEGER NOT NULL DEFAULT 1,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (project_id, job_id)
        REFERENCES analysis_job(project_id, id) ON DELETE CASCADE,
    FOREIGN KEY (project_id, job_id, attempt_id)
        REFERENCES analysis_job_attempt(project_id, job_id, id) ON DELETE CASCADE,
    CONSTRAINT project_event_attempt_has_job CHECK (attempt_id IS NULL OR job_id IS NOT NULL),
    CONSTRAINT project_event_type_shape CHECK (
        event_type ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$'
        AND char_length(event_type) <= 150
    ),
    CONSTRAINT project_event_payload_version_positive CHECK (payload_version > 0),
    CONSTRAINT project_event_payload_object CHECK (jsonb_typeof(payload) = 'object')
);

CREATE INDEX project_event_replay_idx ON project_event (project_id, id);
CREATE INDEX project_event_job_idx ON project_event (job_id, id) WHERE job_id IS NOT NULL;

-- migrate:down

DROP TABLE project_event;
DROP TABLE project_analysis_result;
DROP TABLE analysis_job_artifact;
DROP TABLE analysis_artifact;
ALTER TABLE analysis_job DROP CONSTRAINT analysis_job_success_consistent;
ALTER TABLE analysis_job DROP CONSTRAINT analysis_job_winning_attempt_fk;
ALTER TABLE analysis_job DROP COLUMN winning_attempt_id;
DROP TABLE analysis_job_attempt;
DROP TABLE analysis_job_dependency;
DROP TABLE analysis_job;
DROP TABLE analysis_definition;
ALTER TABLE source_media DROP CONSTRAINT source_media_project_identity;
DROP TYPE project_event_source;
DROP TYPE analysis_artifact_kind;
DROP TYPE analysis_error_kind;
DROP TYPE analysis_attempt_state;
DROP TYPE analysis_job_state;
DROP TYPE analysis_resource_class;
