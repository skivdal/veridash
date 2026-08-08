-- migrate:up

ALTER TABLE analysis_job
DROP CONSTRAINT analysis_job_project_id_source_media_id_module_id_cache_key_key;

DROP INDEX analysis_job_cache_lookup_idx;

ALTER TABLE analysis_job RENAME COLUMN cache_key TO request_key;
ALTER TABLE analysis_job
RENAME CONSTRAINT analysis_job_cache_key_shape TO analysis_job_request_key_shape;

ALTER TABLE analysis_job ADD COLUMN cache_key TEXT;

UPDATE analysis_job AS job
SET cache_key = job.request_key;

ALTER TABLE analysis_job
ADD CONSTRAINT analysis_job_cache_key_shape CHECK (
    cache_key IS NULL OR cache_key ~ '^[0-9a-f]{64}$'
);

ALTER TABLE analysis_job
ADD CONSTRAINT analysis_job_ready_cache_identity CHECK (
    state NOT IN ('ready', 'running', 'retry_wait', 'succeeded') OR cache_key IS NOT NULL
);

ALTER TABLE analysis_job
ADD CONSTRAINT analysis_job_project_request_identity
UNIQUE (project_id, source_media_id, module_id, request_key);

CREATE INDEX analysis_job_cache_lookup_idx
ON analysis_job (cache_key, finished_at DESC)
WHERE state = 'succeeded' AND cache_key IS NOT NULL;

-- migrate:down

DROP INDEX analysis_job_cache_lookup_idx;

ALTER TABLE analysis_job
DROP CONSTRAINT analysis_job_project_request_identity;
ALTER TABLE analysis_job
DROP CONSTRAINT analysis_job_ready_cache_identity;
ALTER TABLE analysis_job
DROP CONSTRAINT analysis_job_cache_key_shape;

ALTER TABLE analysis_job DROP COLUMN cache_key;
ALTER TABLE analysis_job RENAME COLUMN request_key TO cache_key;
ALTER TABLE analysis_job
RENAME CONSTRAINT analysis_job_request_key_shape TO analysis_job_cache_key_shape;

ALTER TABLE analysis_job
ADD CONSTRAINT analysis_job_project_id_source_media_id_module_id_cache_key_key
UNIQUE (project_id, source_media_id, module_id, cache_key);

CREATE INDEX analysis_job_cache_lookup_idx
ON analysis_job (cache_key, finished_at DESC)
WHERE state = 'succeeded';
