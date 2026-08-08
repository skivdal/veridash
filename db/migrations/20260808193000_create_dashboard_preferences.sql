-- migrate:up

CREATE TABLE user_dashboard_preference (
    user_id BIGINT PRIMARY KEY REFERENCES app_user(id) ON DELETE RESTRICT,
    module_order JSONB NOT NULL,
    hidden_modules JSONB NOT NULL DEFAULT '[]'::jsonb,
    revision BIGINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT dashboard_preference_order_array CHECK (jsonb_typeof(module_order) = 'array'),
    CONSTRAINT dashboard_preference_hidden_array CHECK (jsonb_typeof(hidden_modules) = 'array'),
    CONSTRAINT dashboard_preference_revision_positive CHECK (revision > 0),
    CONSTRAINT dashboard_preference_document_bounds CHECK (
        jsonb_array_length(module_order) <= 50
        AND jsonb_array_length(hidden_modules) <= 50
    )
);

-- migrate:down

DROP TABLE user_dashboard_preference;
