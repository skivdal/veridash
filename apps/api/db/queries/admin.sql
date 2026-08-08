-- name: ListAdminUsers :many
SELECT
    app_user.id,
    app_user.username,
    app_user.email,
    app_user.is_enabled,
    app_user.is_admin,
    app_user.last_login_at,
    app_user.created_at,
    count(project.id)::bigint AS project_count
FROM app_user
LEFT JOIN project ON project.user_id = app_user.id
GROUP BY app_user.id
ORDER BY app_user.created_at ASC, app_user.id ASC;

-- name: GetAdminUser :one
SELECT
    app_user.id,
    app_user.username,
    app_user.email,
    app_user.is_enabled,
    app_user.is_admin,
    app_user.last_login_at,
    app_user.created_at,
    count(project.id)::bigint AS project_count
FROM app_user
LEFT JOIN project ON project.user_id = app_user.id
WHERE app_user.id = sqlc.arg(user_id)
GROUP BY app_user.id
LIMIT 1;

-- name: DeactivateNonAdminUser :one
UPDATE app_user
SET is_enabled = FALSE, updated_at = now()
WHERE id = sqlc.arg(user_id) AND is_enabled AND NOT is_admin
RETURNING id;
