"""Explicit installation of the pinned local transcription model."""

import argparse
import os
import shutil
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

from huggingface_hub import snapshot_download  # pyright: ignore[reportUnknownVariableType]
from veridash_analysis.transcription import (
    DEFAULT_MODEL_PATH,
    MODEL_RECEIPT_FILENAME,
    MODEL_REPOSITORY,
    MODEL_REVISION,
    ModelReceipt,
)


def install_transcription_model(target: Path) -> Path:
    """Download an exact model revision and publish it as one local directory."""
    target = target.resolve()
    target.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    if target.exists():
        _require_expected_receipt(target)
        return target

    staging = target.parent / f".{target.name}.download-{uuid4()}"
    try:
        staging.mkdir(mode=0o750)
        snapshot_download(
            repo_id=MODEL_REPOSITORY,
            revision=MODEL_REVISION,
            local_dir=staging,
        )
        _require_model_files(staging)
        (staging / MODEL_RECEIPT_FILENAME).write_text(
            ModelReceipt(
                repository=MODEL_REPOSITORY,
                revision=MODEL_REVISION,
            ).model_dump_json(indent=2)
            + "\n",
            encoding="utf-8",
        )
        os.rename(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target


def _require_expected_receipt(target: Path) -> None:
    receipt_path = target / MODEL_RECEIPT_FILENAME
    try:
        receipt = ModelReceipt.model_validate_json(receipt_path.read_bytes())
    except (FileNotFoundError, OSError, ValueError) as exception:
        raise RuntimeError(
            f"refusing to replace existing model directory without a valid receipt: {target}"
        ) from exception
    if receipt.repository != MODEL_REPOSITORY or receipt.revision != MODEL_REVISION:
        raise RuntimeError(f"existing model directory contains a different revision: {target}")
    _require_model_files(target)


def _require_model_files(target: Path) -> None:
    for filename in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"):
        path = target / filename
        if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
            raise RuntimeError(f"downloaded model is missing {filename}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download the exact local model used by VeriDash transcription"
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path(os.environ.get("VERIDASH_TRANSCRIPTION_MODEL_PATH", DEFAULT_MODEL_PATH)),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    target = install_transcription_model(build_parser().parse_args(argv).target)
    print(f"Installed {MODEL_REPOSITORY}@{MODEL_REVISION} at {target}")


if __name__ == "__main__":
    main()
