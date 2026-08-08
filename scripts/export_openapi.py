"""Export the API schema deterministically for frontend client generation."""

import json
from pathlib import Path

from veridash_api.main import app

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "web" / "openapi.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
