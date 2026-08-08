"""Administrator-only local account management CLI."""

import argparse
import asyncio
import getpass
from typing import NoReturn, cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from veridash_api.auth.passwords import hash_password
from veridash_api.config import Settings
from veridash_api.db.sqlc.auth import AsyncQuerier
from veridash_api.services.admin import normalize_email
from veridash_api.services.auth import normalize_username


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="veridash-admin")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create-user")
    create_parser.add_argument("username")
    create_parser.add_argument("email")
    create_parser.add_argument(
        "--admin",
        action="store_true",
        help="grant access to the user-administration dashboard",
    )
    reset_parser = subparsers.add_parser("reset-password")
    reset_parser.add_argument("username")
    return parser


def _fail(message: str) -> NoReturn:
    raise SystemExit(message)


def _prompt_password() -> str:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Repeat password: ")
    if password != confirmation:
        _fail("Passwords do not match")
    try:
        hash_password(password)
    except ValueError as exception:
        _fail(str(exception))
    return password


async def _run_command(
    command: str,
    username: str,
    password: str,
    *,
    email: str | None,
    is_admin: bool,
) -> None:
    settings = Settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            queries = AsyncQuerier(connection)
            normalized_username = normalize_username(username)
            encoded_password = hash_password(password)
            if command == "create-user":
                if email is None:
                    raise RuntimeError("create-user requires an email address")
                try:
                    normalized_email = normalize_email(email)
                except ValueError as exception:
                    _fail(str(exception))
                try:
                    user = await queries.create_user(
                        username=normalized_username,
                        email=normalized_email,
                        password_hash=encoded_password,
                        is_admin=is_admin,
                    )
                except IntegrityError:
                    _fail(f"User {normalized_username!r} already exists")
                if user is None:
                    raise RuntimeError("INSERT ... RETURNING unexpectedly returned no user")
                print(f"Created user {user.username!r}")
                return

            user = await queries.get_user_by_username(username=normalized_username)
            if user is None:
                _fail(f"User {normalized_username!r} does not exist")
            await queries.update_user_password(password_hash=encoded_password, user_id=user.id)
            await queries.revoke_user_sessions(user_id=user.id)
            print(f"Reset password and revoked sessions for {user.username!r}")
    finally:
        await engine.dispose()


def run() -> None:
    args = _parser().parse_args()
    command = cast(str, args.command)
    username = cast(str, args.username)
    email = cast(str | None, getattr(args, "email", None))
    is_admin = cast(bool, getattr(args, "admin", False))
    password = _prompt_password()
    asyncio.run(
        _run_command(
            command,
            username,
            password,
            email=email,
            is_admin=is_admin,
        )
    )


if __name__ == "__main__":
    run()
