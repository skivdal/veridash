"""Validate invariants that dbmate 2.33 does not enforce itself."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "db" / "migrations"
FILENAME = re.compile(r"^(?P<version>\d{14})_[a-z0-9_]+\.sql$")


def main() -> None:
    versions: dict[str, Path] = {}
    errors: list[str] = []

    for migration in sorted(MIGRATIONS.glob("*.sql")):
        match = FILENAME.fullmatch(migration.name)
        if match is None:
            errors.append(f"invalid migration filename: {migration.name}")
            continue

        version = match.group("version")
        if previous := versions.get(version):
            errors.append(
                f"duplicate migration version {version}: {previous.name}, {migration.name}"
            )
        versions[version] = migration

        contents = migration.read_text(encoding="utf-8")
        if "-- migrate:up" not in contents:
            errors.append(f"missing migrate:up directive: {migration.name}")
        if "-- migrate:down" not in contents:
            errors.append(f"missing migrate:down directive: {migration.name}")

    if not versions:
        errors.append("no database migrations found")
    if errors:
        raise RuntimeError("Invalid dbmate migrations:\n" + "\n".join(errors))


if __name__ == "__main__":
    main()
