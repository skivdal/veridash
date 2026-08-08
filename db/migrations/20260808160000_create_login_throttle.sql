-- migrate:up

CREATE TABLE login_throttle (
    remote_address TEXT PRIMARY KEY,
    window_started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    failed_attempts INTEGER NOT NULL DEFAULT 1,
    locked_until TIMESTAMPTZ,
    CONSTRAINT login_throttle_address_not_blank CHECK (char_length(btrim(remote_address)) > 0),
    CONSTRAINT login_throttle_attempts_positive CHECK (failed_attempts > 0)
);

CREATE INDEX login_throttle_locked_idx
ON login_throttle (locked_until)
WHERE locked_until IS NOT NULL;

-- migrate:down

DROP TABLE login_throttle;
