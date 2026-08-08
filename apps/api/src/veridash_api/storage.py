"""Configured blob-storage dependency."""

from typing import Annotated, cast

from fastapi import Depends, Request
from veridash_storage import UploadBlobStore


def get_blob_store(request: Request) -> UploadBlobStore:
    return cast(UploadBlobStore, request.app.state.blob_store)


ApiBlobStore = Annotated[UploadBlobStore, Depends(get_blob_store)]
