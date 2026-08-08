import pytest
from veridash_api.auth.passwords import hash_password, verify_password
from veridash_api.auth.tokens import (
    csrf_token_matches,
    derive_csrf_token,
    hash_session_token,
    new_session_token,
)


def test_passwords_are_argon2id_hashed_and_verifiable() -> None:
    encoded = hash_password("correct horse battery staple")

    assert encoded.startswith("$argon2id$")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_new_password_policy_rejects_short_values() -> None:
    with pytest.raises(ValueError, match="between 12 and 1024"):
        hash_password("too-short")


def test_session_and_csrf_tokens_are_linked_without_reusing_the_session_secret() -> None:
    session_token = new_session_token()
    csrf_token = derive_csrf_token(session_token)

    assert csrf_token != session_token
    assert len(hash_session_token(session_token)) == 32
    assert csrf_token_matches(session_token, csrf_token, csrf_token)
    assert not csrf_token_matches(session_token, csrf_token, "wrong")
