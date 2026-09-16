"""Password hashing policy."""

from pwdlib import PasswordHash

MINIMUM_PASSWORD_LENGTH = 12
MAXIMUM_PASSWORD_LENGTH = 1024
PASSWORD_HASH = PasswordHash.recommended()


def validate_new_password(password: str) -> None:
    """Reject passwords that are impractical or too short for an account."""
    if not MINIMUM_PASSWORD_LENGTH <= len(password) <= MAXIMUM_PASSWORD_LENGTH:
        message = (
            f"password must contain between {MINIMUM_PASSWORD_LENGTH} "
            f"and {MAXIMUM_PASSWORD_LENGTH} characters"
        )
        raise ValueError(message)


def hash_password(password: str) -> str:
    validate_new_password(password)
    return PASSWORD_HASH.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    return PASSWORD_HASH.verify(password, encoded_hash)
