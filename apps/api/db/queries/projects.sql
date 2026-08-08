-- name: CreateProject :one
INSERT INTO project (id, user_id, title)
VALUES (sqlc.arg(id), sqlc.arg(user_id), sqlc.arg(title))
RETURNING id, user_id, title, state, created_at, updated_at, archived_at;

-- name: GetProject :one
SELECT id, user_id, title, state, created_at, updated_at, archived_at
FROM project
WHERE id = sqlc.arg(id) AND user_id = sqlc.arg(user_id)
LIMIT 1;

-- name: ListProjects :many
SELECT id, user_id, title, state, created_at, updated_at, archived_at
FROM project
WHERE user_id = sqlc.arg(user_id)
ORDER BY updated_at DESC, id DESC;

-- name: RenameProject :one
UPDATE project
SET title = sqlc.arg(title), updated_at = now()
WHERE id = sqlc.arg(id) AND user_id = sqlc.arg(user_id)
RETURNING id, user_id, title, state, created_at, updated_at, archived_at;

-- name: ArchiveProject :one
UPDATE project
SET
    state = 'archived',
    archived_at = COALESCE(archived_at, now()),
    updated_at = CASE WHEN state = 'active' THEN now() ELSE updated_at END
WHERE id = sqlc.arg(id) AND user_id = sqlc.arg(user_id)
RETURNING id, user_id, title, state, created_at, updated_at, archived_at;

-- name: RestoreProject :one
UPDATE project
SET
    state = 'active',
    archived_at = NULL,
    updated_at = CASE WHEN state = 'archived' THEN now() ELSE updated_at END
WHERE id = sqlc.arg(id) AND user_id = sqlc.arg(user_id)
RETURNING id, user_id, title, state, created_at, updated_at, archived_at;

-- name: GetProjectNote :one
SELECT
    project.id AS project_id,
    COALESCE(note.body, '') AS body,
    COALESCE(note.revision, 0)::BIGINT AS revision,
    COALESCE(note.updated_at, project.created_at) AS updated_at
FROM project
LEFT JOIN project_note AS note ON note.project_id = project.id
WHERE project.id = sqlc.arg(project_id) AND project.user_id = sqlc.arg(user_id)
LIMIT 1;

-- name: SaveProjectNote :one
WITH authorized AS (
    SELECT project.id
    FROM project
    WHERE project.id = sqlc.arg(project_id) AND project.user_id = sqlc.arg(user_id)
), saved AS (
    INSERT INTO project_note (project_id, body, revision)
    SELECT authorized.id, sqlc.arg(body), 1
    FROM authorized
    WHERE
        sqlc.arg(expected_revision)::BIGINT = 0
        OR EXISTS (
            SELECT 1
            FROM project_note AS current_note
            WHERE
                current_note.project_id = authorized.id
                AND current_note.revision = sqlc.arg(expected_revision)
        )
    ON CONFLICT (project_id) DO UPDATE
    SET
        body = EXCLUDED.body,
        revision = project_note.revision + 1,
        updated_at = now()
    WHERE project_note.revision = sqlc.arg(expected_revision)
    RETURNING project_id, body, revision, updated_at
), touched_project AS (
    UPDATE project
    SET updated_at = saved.updated_at
    FROM saved
    WHERE project.id = saved.project_id
), event AS (
    INSERT INTO project_event (project_id, event_type, source, payload)
    SELECT
        saved.project_id,
        'project.note_updated',
        'user',
        jsonb_build_object('revision', saved.revision)
    FROM saved
)
SELECT project_id, body, revision, updated_at FROM saved;
