-- migrate:up

CREATE TYPE project_state AS ENUM ('active', 'archived');
CREATE TYPE media_upload_state AS ENUM ('pending', 'uploaded', 'failed');

CREATE TABLE app_user (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT app_user_username_normalized CHECK (username = lower(btrim(username))),
    CONSTRAINT app_user_username_length CHECK (char_length(username) BETWEEN 1 AND 128)
);

CREATE TABLE user_session (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    token_hash BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    CONSTRAINT user_session_expiry_after_creation CHECK (expires_at > created_at)
);

CREATE INDEX user_session_active_user_idx
ON user_session (user_id, expires_at)
WHERE revoked_at IS NULL;

CREATE TABLE project (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES app_user(id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    state project_state NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    CONSTRAINT project_title_not_blank CHECK (char_length(btrim(title)) BETWEEN 1 AND 200),
    CONSTRAINT project_archive_consistent CHECK (
        (state = 'active' AND archived_at IS NULL)
        OR (state = 'archived' AND archived_at IS NOT NULL)
    )
);

CREATE INDEX project_user_updated_idx ON project (user_id, updated_at DESC, id DESC);

CREATE TABLE source_media (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL UNIQUE REFERENCES project(id) ON DELETE RESTRICT,
    upload_state media_upload_state NOT NULL DEFAULT 'pending',
    original_filename TEXT NOT NULL,
    media_type TEXT,
    size_bytes BIGINT,
    sha256_hex TEXT,
    blob_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    uploaded_at TIMESTAMPTZ,
    failure_message TEXT,
    CONSTRAINT source_media_filename_not_blank CHECK (char_length(btrim(original_filename)) > 0),
    CONSTRAINT source_media_size_nonnegative CHECK (size_bytes IS NULL OR size_bytes >= 0),
    CONSTRAINT source_media_sha256_shape CHECK (
        sha256_hex IS NULL OR sha256_hex ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT source_media_upload_consistent CHECK (
        upload_state <> 'uploaded'
        OR (
            media_type IS NOT NULL
            AND size_bytes IS NOT NULL
            AND sha256_hex IS NOT NULL
            AND blob_key IS NOT NULL
            AND uploaded_at IS NOT NULL
            AND failure_message IS NULL
        )
    )
);

-- migrate:down

DROP TABLE source_media;
DROP TABLE project;
DROP TABLE user_session;
DROP TABLE app_user;
DROP TYPE media_upload_state;
DROP TYPE project_state;
