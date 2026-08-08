"""Single-host content-addressed filesystem storage."""

import asyncio
import hashlib
import os
import re
from collections.abc import AsyncIterable
from pathlib import Path
from uuid import UUID, uuid4

import anyio

from veridash_storage.contracts import BlobRef, BlobTooLargeError, StagedBlob

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COPY_CHUNK_BYTES = 1024 * 1024


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class FilesystemBlobStore:
    """Publish immutable blobs below one absolute, operator-owned data root."""

    def __init__(self, root: Path) -> None:
        if not root.is_absolute():
            raise ValueError("blob storage root must be an absolute path")
        self._root = root.resolve()
        self._blob_root = self._root / "blobs" / "sha256"
        self._staging_root = self._root / "staging"
        self._upload_staging_root = self._staging_root / "uploads"
        self._blob_root.mkdir(mode=0o750, parents=True, exist_ok=True)
        self._upload_staging_root.mkdir(mode=0o750, parents=True, exist_ok=True)

    def _blob_path(self, sha256: str) -> Path:
        if SHA256_PATTERN.fullmatch(sha256) is None:
            raise ValueError("invalid SHA-256 blob identity")
        return self._blob_root / sha256[:2] / sha256[2:4] / sha256

    def staging_path(self, staging_id: str) -> Path:
        normalized_id = str(UUID(staging_id))
        return self._upload_staging_root / f"{normalized_id}.part"

    async def stage(
        self,
        staging_id: str,
        chunks: AsyncIterable[bytes],
        *,
        max_bytes: int,
    ) -> StagedBlob:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")

        destination = self.staging_path(staging_id)
        temporary = destination.with_name(f".{destination.name}.{uuid4()}.tmp")
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            async with await anyio.open_file(temporary, "wb") as output:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    size_bytes += len(chunk)
                    if size_bytes > max_bytes:
                        raise BlobTooLargeError("upload exceeds configured byte limit")
                    digest.update(chunk)
                    await output.write(chunk)
                await output.flush()
                await asyncio.to_thread(os.fsync, output.wrapped.fileno())
            os.replace(temporary, destination)
            await asyncio.to_thread(_fsync_directory, destination.parent)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

        return StagedBlob(sha256=digest.hexdigest(), size_bytes=size_bytes)

    def publish(self, staging_path: Path, *, media_type: str) -> BlobRef:
        if staging_path.is_symlink():
            raise ValueError("staging path must not be a symbolic link")
        resolved_staging = staging_path.resolve(strict=True)
        if not resolved_staging.is_file():
            raise ValueError("staging path must be a regular file")
        try:
            resolved_staging.relative_to(self._staging_root)
        except ValueError as exception:
            raise ValueError("staging path is outside the storage staging root") from exception

        digest = hashlib.sha256()
        size_bytes = 0
        with resolved_staging.open("rb") as source:
            while chunk := source.read(COPY_CHUNK_BYTES):
                digest.update(chunk)
                size_bytes += len(chunk)
        sha256 = digest.hexdigest()
        destination = self._blob_path(sha256)
        destination.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
        try:
            os.link(resolved_staging, destination)
        except FileExistsError:
            if destination.stat().st_size != size_bytes:
                raise RuntimeError("content-addressed blob has an unexpected size") from None
        destination.chmod(0o440)
        _fsync_directory(destination.parent)
        return BlobRef(sha256=sha256, size_bytes=size_bytes, media_type=media_type)

    def open(self, sha256: str):
        return self._blob_path(sha256).open("rb")

    def exists(self, sha256: str) -> bool:
        return self._blob_path(sha256).is_file()

    def materialize(self, sha256: str, destination: Path) -> Path:
        """Hard-link an immutable blob to one explicit worker-owned path."""
        source = self._blob_path(sha256).resolve(strict=True)
        resolved_parent = destination.parent.resolve(strict=True)
        resolved_destination = resolved_parent / destination.name
        if resolved_destination.exists():
            raise FileExistsError("materialized blob destination already exists")
        os.link(source, resolved_destination)
        return resolved_destination

    def discard_staging(self, staging_id: str) -> None:
        staging_path = self.staging_path(staging_id)
        if staging_path.is_file():
            staging_path.unlink()
            _fsync_directory(staging_path.parent)
