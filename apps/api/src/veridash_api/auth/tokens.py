"""Opaque session and double-submit CSRF token handling."""

import hashlib
import hmac
import secrets

SESSION_TOKEN_BYTES = 32
CSRF_CONTEXT = b"veridash-csrf-v1"


def new_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> memoryview:
    return memoryview(hashlib.sha256(token.encode("utf-8")).digest())


def derive_csrf_token(session_token: str) -> str:
    return hmac.new(session_token.encode("utf-8"), CSRF_CONTEXT, hashlib.sha256).hexdigest()


def csrf_token_matches(session_token: str, cookie_token: str, header_token: str) -> bool:
    expected = derive_csrf_token(session_token)
    return hmac.compare_digest(cookie_token, expected) and hmac.compare_digest(
        header_token,
        expected,
    )
