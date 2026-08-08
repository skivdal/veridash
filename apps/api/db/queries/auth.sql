-- name: CreateUser :one
INSERT INTO app_user (username, email, password_hash, is_admin)
VALUES (
    sqlc.arg(username),
    sqlc.arg(email),
    sqlc.arg(password_hash),
    sqlc.arg(is_admin)
)
RETURNING
    id, username, email, password_hash, is_enabled, is_admin, last_login_at,
    created_at, updated_at;

-- name: GetUserByUsername :one
SELECT
    id, username, email, password_hash, is_enabled, is_admin, last_login_at,
    created_at, updated_at
FROM app_user
WHERE username = sqlc.arg(username)
LIMIT 1;

-- name: UpdateUserPassword :exec
UPDATE app_user
SET password_hash = sqlc.arg(password_hash), updated_at = now()
WHERE id = sqlc.arg(user_id);

-- name: CreateSession :one
INSERT INTO user_session (id, user_id, token_hash, expires_at)
SELECT
    sqlc.arg(id),
    sqlc.arg(user_id),
    sqlc.arg(token_hash),
    sqlc.arg(expires_at)
FROM app_user
WHERE id = sqlc.arg(user_id) AND is_enabled
RETURNING id, user_id, token_hash, created_at, expires_at, last_seen_at, revoked_at;

-- name: GetActiveSessionUser :one
SELECT
    app_user.id AS user_id,
    app_user.username,
    app_user.email,
    app_user.is_admin,
    user_session.id AS session_id,
    user_session.expires_at
FROM user_session
JOIN app_user ON app_user.id = user_session.user_id
WHERE
    user_session.token_hash = sqlc.arg(token_hash)
    AND user_session.revoked_at IS NULL
    AND user_session.expires_at > now()
    AND app_user.is_enabled
LIMIT 1;

-- name: TouchSession :exec
UPDATE user_session
SET last_seen_at = now()
WHERE
    token_hash = sqlc.arg(token_hash)
    AND revoked_at IS NULL
    AND expires_at > now()
    AND last_seen_at < now() - interval '5 minutes';

-- name: RevokeSession :exec
UPDATE user_session
SET revoked_at = now()
WHERE token_hash = sqlc.arg(token_hash) AND revoked_at IS NULL;

-- name: RevokeUserSessions :exec
UPDATE user_session
SET revoked_at = now()
WHERE user_id = sqlc.arg(user_id) AND revoked_at IS NULL;

-- name: RecordSuccessfulLogin :exec
UPDATE app_user
SET last_login_at = now()
WHERE id = sqlc.arg(user_id);

-- name: IsLoginBlocked :one
SELECT EXISTS (
    SELECT 1
    FROM login_throttle
    WHERE
        remote_address = sqlc.arg(remote_address)
        AND locked_until > now()
) AS is_blocked;

-- name: RecordLoginFailure :exec
INSERT INTO login_throttle (remote_address)
VALUES (sqlc.arg(remote_address))
ON CONFLICT (remote_address) DO UPDATE
SET
    window_started_at = CASE
        WHEN login_throttle.window_started_at < now() - interval '15 minutes' THEN now()
        ELSE login_throttle.window_started_at
    END,
    failed_attempts = CASE
        WHEN login_throttle.window_started_at < now() - interval '15 minutes' THEN 1
        ELSE login_throttle.failed_attempts + 1
    END,
    locked_until = CASE
        WHEN login_throttle.window_started_at < now() - interval '15 minutes' THEN NULL
        WHEN login_throttle.failed_attempts + 1 >= 5 THEN now() + interval '15 minutes'
        ELSE login_throttle.locked_until
    END;

-- name: ClearLoginFailures :exec
DELETE FROM login_throttle
WHERE remote_address = sqlc.arg(remote_address);
