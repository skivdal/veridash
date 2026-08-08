-- migrate:up

CREATE TABLE project_note (
    project_id UUID PRIMARY KEY REFERENCES project(id) ON DELETE RESTRICT,
    body TEXT NOT NULL DEFAULT '',
    revision BIGINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT project_note_body_length CHECK (char_length(body) <= 100000),
    CONSTRAINT project_note_revision_positive CHECK (revision > 0)
);

-- migrate:down

DROP TABLE project_note;
