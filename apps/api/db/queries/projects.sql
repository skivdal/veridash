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
