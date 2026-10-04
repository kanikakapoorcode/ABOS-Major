"""
Unit tests for authentication and security helpers.
"""

import pytest
from jose import JWTError
from backend.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_password_hashing_and_verification():
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_access_and_refresh_tokens():
    user_id = "user-12345"

    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    access_payload = decode_token(access_token)
    assert access_payload["sub"] == user_id
    assert access_payload["type"] == "access"
    assert "exp" in access_payload

    refresh_payload = decode_token(refresh_token)
    assert refresh_payload["sub"] == user_id
    assert refresh_payload["type"] == "refresh"
    assert "exp" in refresh_payload


def test_decode_invalid_jwt():
    with pytest.raises(JWTError):
        decode_token("invalid.jwt.token")
