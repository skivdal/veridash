"""Worker resource classifications and single-VPS defaults."""

import os
from enum import StrEnum


class ResourceClass(StrEnum):
    """Execution pools with different capability and isolation policies."""

    CPU = "cpu"
    GPU = "gpu"
    TRANSLATION = "translation"


def default_concurrency(resource: ResourceClass) -> int:
    """Return conservative defaults; production can lower CPU concurrency."""
    match resource:
        case ResourceClass.GPU:
            return 2
        case ResourceClass.TRANSLATION:
            return 1
        case ResourceClass.CPU:
            return max(1, (os.cpu_count() or 2) - 1)
