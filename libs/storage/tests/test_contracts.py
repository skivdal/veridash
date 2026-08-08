from veridash_storage import BlobRef


def test_blob_reference_is_immutable() -> None:
    ref = BlobRef(sha256="0" * 64, size_bytes=12, media_type="video/mp4")

    assert ref.size_bytes == 12
