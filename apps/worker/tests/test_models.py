from pathlib import Path

import pytest
from veridash_analysis.transcription import (
    MODEL_RECEIPT_FILENAME,
    MODEL_REPOSITORY,
    MODEL_REVISION,
)
from veridash_worker import models


def test_model_install_is_pinned_atomic_and_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    downloads = 0

    def fake_download(*, repo_id: str, revision: str, local_dir: Path) -> str:
        nonlocal downloads
        downloads += 1
        assert repo_id == MODEL_REPOSITORY
        assert revision == MODEL_REVISION
        for filename in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"):
            (local_dir / filename).write_bytes(b"model")
        return str(local_dir)

    monkeypatch.setattr(models, "snapshot_download", fake_download)
    target = tmp_path / "models" / "medium"

    assert models.install_transcription_model(target) == target.resolve()
    assert models.install_transcription_model(target) == target.resolve()

    assert downloads == 1
    assert (target / MODEL_RECEIPT_FILENAME).is_file()
    assert not any(path.name.startswith(".medium.download-") for path in target.parent.iterdir())


def test_model_install_refuses_an_unrecognized_existing_directory(tmp_path: Path) -> None:
    target = tmp_path / "model"
    target.mkdir()

    with pytest.raises(RuntimeError, match="refusing to replace"):
        models.install_transcription_model(target)
