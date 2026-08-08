"""Backend-neutral immutable blob-storage types."""

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol


@dataclass(frozen=True, slots=True)
class BlobRef:
    """Identity and representation metadata for one immutable blob."""

    sha256: str
    size_bytes: int
    media_type: str


class BlobStore(Protocol):
    """Storage operations required by API and worker processes."""

    def open(self, sha256: str) -> BinaryIO: ...

    def publish(self, staging_path: Path, *, media_type: str) -> BlobRef: ...

    def exists(self, sha256: str) -> bool: ...
