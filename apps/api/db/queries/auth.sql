-- name: CreateUser :one
INSERT INTO app_user (username, password_hash)
VALUES (sqlc.arg(username), sqlc.arg(password_hash))
RETURNING id, username, password_hash, is_enabled, created_at, updated_at;

-- name: GetUserByUsername :one
SELECT id, username, password_hash, is_enabled, created_at, updated_at
FROM app_user
WHERE username = sqlc.arg(username)
LIMIT 1;
