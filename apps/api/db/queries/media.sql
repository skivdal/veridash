-- name: CreateSourceMedia :one
INSERT INTO source_media (id, project_id, original_filename)
SELECT sqlc.arg(id), project.id, sqlc.arg(original_filename)
FROM project
WHERE
    project.id = sqlc.arg(project_id)
    AND project.user_id = sqlc.arg(user_id)
    AND project.state = 'active'
ON CONFLICT (project_id) DO UPDATE
SET original_filename = EXCLUDED.original_filename
WHERE source_media.upload_state <> 'uploaded'
RETURNING
    id, project_id, upload_state, original_filename, media_type, size_bytes,
    sha256_hex, blob_key, created_at, uploaded_at, failure_message;

-- name: GetSourceMediaForProject :one
SELECT
    source_media.id, source_media.project_id, source_media.upload_state,
    source_media.original_filename, source_media.media_type, source_media.size_bytes,
    source_media.sha256_hex, source_media.blob_key, source_media.created_at,
    source_media.uploaded_at, source_media.failure_message
FROM source_media
JOIN project ON project.id = source_media.project_id
WHERE project.id = sqlc.arg(project_id) AND project.user_id = sqlc.arg(user_id)
LIMIT 1;

-- name: GetSourceMedia :one
SELECT
    source_media.id, source_media.project_id, source_media.upload_state,
    source_media.original_filename, source_media.media_type, source_media.size_bytes,
    source_media.sha256_hex, source_media.blob_key, source_media.created_at,
    source_media.uploaded_at, source_media.failure_message
FROM source_media
JOIN project ON project.id = source_media.project_id
WHERE source_media.id = sqlc.arg(id) AND project.user_id = sqlc.arg(user_id)
LIMIT 1;

-- name: RecordUploadContent :one
UPDATE source_media
SET
    upload_state = 'pending',
    media_type = sqlc.arg(media_type),
    size_bytes = sqlc.arg(size_bytes),
    sha256_hex = sqlc.arg(sha256_hex),
    blob_key = NULL,
    uploaded_at = NULL,
    failure_message = NULL
WHERE
    source_media.id = sqlc.arg(media_id)
    AND upload_state <> 'uploaded'
    AND project_id IN (
        SELECT id FROM project WHERE user_id = sqlc.arg(user_id) AND state = 'active'
    )
RETURNING
    id, project_id, upload_state, original_filename, media_type, size_bytes,
    sha256_hex, blob_key, created_at, uploaded_at, failure_message;

-- name: MarkSourceMediaUploaded :one
UPDATE source_media
SET
    upload_state = 'uploaded',
    media_type = sqlc.arg(media_type),
    size_bytes = sqlc.arg(size_bytes),
    sha256_hex = sqlc.arg(sha256_hex),
    blob_key = sqlc.arg(blob_key),
    uploaded_at = now(),
    failure_message = NULL
WHERE
    source_media.id = sqlc.arg(media_id)
    AND upload_state <> 'uploaded'
    AND sha256_hex = sqlc.arg(sha256_hex)
    AND size_bytes = sqlc.arg(size_bytes)
    AND project_id IN (
        SELECT id FROM project WHERE user_id = sqlc.arg(user_id) AND state = 'active'
    )
RETURNING
    id, project_id, upload_state, original_filename, media_type, size_bytes,
    sha256_hex, blob_key, created_at, uploaded_at, failure_message;

-- name: MarkSourceMediaFailed :one
UPDATE source_media
SET
    upload_state = 'failed',
    blob_key = NULL,
    uploaded_at = NULL,
    failure_message = sqlc.arg(failure_message)
WHERE
    source_media.id = sqlc.arg(media_id)
    AND upload_state <> 'uploaded'
    AND project_id IN (
        SELECT id FROM project WHERE user_id = sqlc.arg(user_id) AND state = 'active'
    )
RETURNING
    id, project_id, upload_state, original_filename, media_type, size_bytes,
    sha256_hex, blob_key, created_at, uploaded_at, failure_message;
