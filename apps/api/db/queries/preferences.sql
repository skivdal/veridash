-- name: GetDashboardPreference :one
SELECT
    app_user.id AS user_id,
    COALESCE(preference.module_order, '[]'::JSONB) AS module_order,
    COALESCE(preference.hidden_modules, '[]'::JSONB) AS hidden_modules,
    COALESCE(preference.revision, 0)::BIGINT AS revision,
    COALESCE(preference.updated_at, app_user.created_at) AS updated_at
FROM app_user
LEFT JOIN user_dashboard_preference AS preference
    ON preference.user_id = app_user.id
WHERE app_user.id = sqlc.arg(user_id)
LIMIT 1;

-- name: SaveDashboardPreference :one
WITH saved AS (
    INSERT INTO user_dashboard_preference (
        user_id,
        module_order,
        hidden_modules,
        revision
    )
    SELECT
        app_user.id,
        sqlc.arg(module_order),
        sqlc.arg(hidden_modules),
        1
    FROM app_user
    WHERE
        app_user.id = sqlc.arg(user_id)
        AND (
            sqlc.arg(expected_revision)::BIGINT = 0
            OR EXISTS (
                SELECT 1
                FROM user_dashboard_preference AS current_preference
                WHERE
                    current_preference.user_id = app_user.id
                    AND current_preference.revision = sqlc.arg(expected_revision)
            )
        )
    ON CONFLICT (user_id) DO UPDATE
    SET
        module_order = EXCLUDED.module_order,
        hidden_modules = EXCLUDED.hidden_modules,
        revision = user_dashboard_preference.revision + 1,
        updated_at = now()
    WHERE user_dashboard_preference.revision = sqlc.arg(expected_revision)
    RETURNING user_id, module_order, hidden_modules, revision, updated_at
)
SELECT * FROM saved;
