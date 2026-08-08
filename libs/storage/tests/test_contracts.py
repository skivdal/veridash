from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
from veridash_storage import BlobRef, BlobTooLargeError, FilesystemBlobStore


def test_blob_reference_is_immutable() -> None:
    ref = BlobRef(sha256="0" * 64, size_bytes=12, media_type="video/mp4")

    assert ref.size_bytes == 12


async def _chunks(*values: bytes) -> AsyncIterator[bytes]:
    for value in values:
        yield value


async def test_filesystem_store_stages_publishes_and_deduplicates(tmp_path: Path) -> None:
    store = FilesystemBlobStore(tmp_path)
    first_id = str(uuid4())
    staged = await store.stage(first_id, _chunks(b"video", b"-bytes"), max_bytes=100)

    assert staged.size_bytes == 11
    published = store.publish(store.staging_path(first_id), media_type="video/mp4")
    assert published.sha256 == staged.sha256
    assert store.exists(staged.sha256)
    with store.open(staged.sha256) as content:
        assert content.read() == b"video-bytes"
    materialized_root = tmp_path / "attempt"
    materialized_root.mkdir()
    materialized = store.materialize(staged.sha256, materialized_root / "source")
    assert materialized.read_bytes() == b"video-bytes"

    second_id = str(uuid4())
    await store.stage(second_id, _chunks(b"video-bytes"), max_bytes=100)
    duplicate = store.publish(store.staging_path(second_id), media_type="video/mp4")
    assert duplicate.sha256 == published.sha256

    store.discard_staging(first_id)
    store.discard_staging(second_id)
    assert store.exists(staged.sha256)


async def test_oversized_stage_never_replaces_existing_content(tmp_path: Path) -> None:
    store = FilesystemBlobStore(tmp_path)
    staging_id = str(uuid4())
    original = await store.stage(staging_id, _chunks(b"original"), max_bytes=100)

    with pytest.raises(BlobTooLargeError):
        await store.stage(staging_id, _chunks(b"12345", b"67890"), max_bytes=8)

    published = store.publish(store.staging_path(staging_id), media_type="video/mp4")
    assert published.sha256 == original.sha256


def test_filesystem_store_rejects_relative_root() -> None:
    with pytest.raises(ValueError, match="absolute"):
        FilesystemBlobStore(Path("relative/data"))
