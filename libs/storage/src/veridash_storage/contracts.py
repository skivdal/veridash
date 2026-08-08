"""Backend-neutral immutable blob-storage types."""

from collections.abc import AsyncIterable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol


@dataclass(frozen=True, slots=True)
class BlobRef:
    """Identity and representation metadata for one immutable blob."""

    sha256: str
    size_bytes: int
    media_type: str


@dataclass(frozen=True, slots=True)
class StagedBlob:
    """Integrity metadata for bytes durably staged under a server-issued ID."""

    sha256: str
    size_bytes: int


class BlobTooLargeError(ValueError):
    """Raised after a staged stream crosses its configured byte limit."""


class BlobStore(Protocol):
    """Storage operations required by API and worker processes."""

    def open(self, sha256: str) -> BinaryIO: ...

    def publish(self, staging_path: Path, *, media_type: str) -> BlobRef: ...

    def exists(self, sha256: str) -> bool: ...

    def materialize(self, sha256: str, destination: Path) -> Path: ...


class UploadBlobStore(BlobStore, Protocol):
    """Blob storage plus durable, replaceable upload staging."""

    async def stage(
        self,
        staging_id: str,
        chunks: AsyncIterable[bytes],
        *,
        max_bytes: int,
    ) -> StagedBlob: ...

    def staging_path(self, staging_id: str) -> Path: ...

    def discard_staging(self, staging_id: str) -> None: ...
