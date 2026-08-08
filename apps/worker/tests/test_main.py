import pytest
from veridash_worker.main import main


def test_gpu_concurrency_may_be_two() -> None:
    main(["--pool", "gpu", "--concurrency", "2"])


def test_gpu_concurrency_cannot_exceed_two() -> None:
    with pytest.raises(SystemExit, match="cannot exceed"):
        main(["--pool", "gpu", "--concurrency", "3"])
