-- migrate:up

ALTER TABLE app_user
ADD COLUMN email TEXT,
ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE,
ADD COLUMN last_login_at TIMESTAMPTZ;

UPDATE app_user
SET
    email = 'legacy-' || id || '@invalid.local',
    is_admin = TRUE;

ALTER TABLE app_user
ALTER COLUMN email SET NOT NULL;

ALTER TABLE app_user
ADD CONSTRAINT app_user_email_normalized CHECK (email = lower(btrim(email))),
ADD CONSTRAINT app_user_email_length CHECK (char_length(email) BETWEEN 3 AND 320),
ADD CONSTRAINT app_user_email_shape CHECK (email ~ '^[^[:space:]@]+@[^[:space:]@]+$'),
ADD CONSTRAINT app_user_email_unique UNIQUE (email);

-- migrate:down

ALTER TABLE app_user
DROP CONSTRAINT app_user_email_unique,
DROP CONSTRAINT app_user_email_shape,
DROP CONSTRAINT app_user_email_length,
DROP CONSTRAINT app_user_email_normalized,
DROP COLUMN last_login_at,
DROP COLUMN is_admin,
DROP COLUMN email;
