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
