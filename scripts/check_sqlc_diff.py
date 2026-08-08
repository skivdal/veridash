"""Fail when committed SQLc output differs from current schema and queries."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = (
    "apps/api/sqlc.yaml",
    "apps/scheduler/sqlc.yaml",
    "apps/worker/sqlc.yaml",
)
SQLC_VERSION_LINE = re.compile(r"^[+-]#   sqlc v\S+\s*$")


def check_config(config: str) -> None:
    result = subprocess.run(
        ["sqlc", "diff", "-f", config],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode == 0:
        return

    changed_lines = [
        line
        for line in result.stdout.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    if changed_lines and all(SQLC_VERSION_LINE.match(line) for line in changed_lines):
        return

    raise RuntimeError(f"SQLc output is stale for {config}:\n{result.stdout}")


def main() -> None:
    for config in CONFIGS:
        check_config(config)


if __name__ == "__main__":
    main()
