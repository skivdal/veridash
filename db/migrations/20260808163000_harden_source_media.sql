-- migrate:up

ALTER TABLE source_media
ADD CONSTRAINT source_media_filename_length
CHECK (char_length(original_filename) <= 512);

ALTER TABLE source_media
ADD CONSTRAINT source_media_media_type_length
CHECK (media_type IS NULL OR char_length(media_type) <= 255);

ALTER TABLE source_media
ADD CONSTRAINT source_media_failure_message_length
CHECK (failure_message IS NULL OR char_length(failure_message) <= 1000);

ALTER TABLE source_media
DROP CONSTRAINT source_media_upload_consistent;

ALTER TABLE source_media
ADD CONSTRAINT source_media_upload_consistent CHECK (
    (
        upload_state = 'pending'
        AND uploaded_at IS NULL
        AND blob_key IS NULL
        AND failure_message IS NULL
        AND (
            (
                media_type IS NULL
                AND size_bytes IS NULL
                AND sha256_hex IS NULL
            )
            OR (
                media_type IS NOT NULL
                AND size_bytes IS NOT NULL
                AND sha256_hex IS NOT NULL
            )
        )
    )
    OR (
        upload_state = 'uploaded'
        AND media_type IS NOT NULL
        AND size_bytes IS NOT NULL
        AND sha256_hex IS NOT NULL
        AND blob_key IS NOT NULL
        AND uploaded_at IS NOT NULL
        AND failure_message IS NULL
    )
    OR (
        upload_state = 'failed'
        AND media_type IS NOT NULL
        AND size_bytes IS NOT NULL
        AND sha256_hex IS NOT NULL
        AND uploaded_at IS NULL
        AND blob_key IS NULL
        AND failure_message IS NOT NULL
    )
);

-- migrate:down

ALTER TABLE source_media
DROP CONSTRAINT source_media_upload_consistent;

ALTER TABLE source_media
ADD CONSTRAINT source_media_upload_consistent CHECK (
    upload_state <> 'uploaded'
    OR (
        media_type IS NOT NULL
        AND size_bytes IS NOT NULL
        AND sha256_hex IS NOT NULL
        AND blob_key IS NOT NULL
        AND uploaded_at IS NOT NULL
        AND failure_message IS NULL
    )
);

ALTER TABLE source_media DROP CONSTRAINT source_media_failure_message_length;
ALTER TABLE source_media DROP CONSTRAINT source_media_media_type_length;
ALTER TABLE source_media DROP CONSTRAINT source_media_filename_length;
