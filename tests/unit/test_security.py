"""
Unit tests for the authentication utilities in backend/utils/auth.py.

This is the module the API actually authenticates through — get_current_user
resolves to verify_token here — so these tests cover the live auth path.

There used to be a second copy of these helpers in backend/core/security.py
that nothing but this test imported. It hashed with passlib instead of raw
bcrypt and its decode_token() never checked the "type" claim, so a refresh
token would have been accepted wherever an access token was expected. It was
deleted rather than fixed: one auth surface is the point.
"""

from datetime import timedelta

import pytest
from jose import jwt

from backend.utils.auth import (
    ALGORITHM,
    BCRYPT_ROUNDS,
    create_access_token,
    create_refresh_token,
    create_tokens,
    get_password_hash,
    validate_password_strength,
    verify_password,
    verify_token,
)

USER = {"sub": "user-123", "email": "student@example.com", "role": "student"}


# ==================== PASSWORDS ====================


def test_password_hashing():
    """Hashing is one-way and verification accepts only the real password."""
    password = "TestPass123!"
    hashed = get_password_hash(password)

    assert hashed != password
    assert hashed.startswith("$2b$")  # bcrypt, not an unsalted digest
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPass123!", hashed) is False


def test_password_hashing_is_salted():
    """Same password, different hash — otherwise hashes are a rainbow table."""
    first = get_password_hash("TestPass123!")
    second = get_password_hash("TestPass123!")

    assert first != second
    assert verify_password("TestPass123!", first) is True
    assert verify_password("TestPass123!", second) is True


def test_password_hashing_uses_configured_work_factor():
    """A low work factor makes offline cracking cheap; keep it pinned."""
    assert BCRYPT_ROUNDS >= 12
    assert f"${BCRYPT_ROUNDS:02d}$" in get_password_hash("TestPass123!")


def test_weak_password_is_rejected_before_hashing():
    """get_password_hash enforces the policy, so no caller can skip it."""
    with pytest.raises(ValueError):
        get_password_hash("short")


def test_password_validation():
    """Test password strength validation."""
    is_valid, error = validate_password_strength("TestPass123!")
    assert is_valid is True
    assert error == ""

    for weak in (
        "short",  # too short
        "alllowercase123!",  # no uppercase
        "ALLUPPERCASE123!",  # no lowercase
        "NoDigitsHere!!!!",  # no digit
        "NoSpecialChars12",  # no special character
    ):
        is_valid, error = validate_password_strength(weak)
        assert is_valid is False, f"{weak!r} should have been rejected"
        assert error


def test_verify_password_rejects_malformed_hash():
    """A corrupt stored hash must deny access, not raise into the handler."""
    assert verify_password("TestPass123!", "not-a-bcrypt-hash") is False


# ==================== TOKENS ====================


def test_create_access_token():
    """Test JWT access token creation."""
    token = create_access_token(USER)

    assert isinstance(token, str)
    assert len(token) > 0

    data = verify_token(token, token_type="access")
    assert data is not None
    assert data.user_id == "user-123"
    assert data.email == "student@example.com"
    assert data.role == "student"


def test_create_refresh_token():
    """Refresh tokens carry a JTI and expiry for rotation tracking."""
    token, token_jti, expires_at = create_refresh_token(USER)

    assert isinstance(token, str)
    assert token_jti
    assert expires_at is not None

    data = verify_token(token, token_type="refresh")
    assert data is not None
    assert data.user_id == "user-123"


def test_create_tokens_returns_a_usable_pair():
    """Test the login helper issues both halves of the session."""
    tokens = create_tokens("user-123", "student@example.com", role="teacher")

    assert tokens.token_type == "bearer"
    assert verify_token(tokens.access_token, token_type="access").role == "teacher"
    assert verify_token(tokens.refresh_token, token_type="refresh").user_id == "user-123"


def test_refresh_token_is_rejected_as_an_access_token():
    """
    Refresh tokens live for days, access tokens for minutes. Accepting one
    where the other is expected would silently stretch a session far past
    its intended lifetime, so the "type" claim has to be enforced.
    """
    refresh_token, _, _ = create_refresh_token(USER)

    assert verify_token(refresh_token, token_type="access") is None


def test_access_token_is_rejected_as_a_refresh_token():
    """The same check in the other direction: no minting from an access token."""
    access_token = create_access_token(USER)

    assert verify_token(access_token, token_type="refresh") is None


def test_verify_token_rejects_garbage():
    """Test verifying an unparseable token fails closed."""
    assert verify_token("invalid_token") is None


def test_verify_token_rejects_a_foreign_signature():
    """
    The signature must actually be checked. A token that is well-formed and
    unexpired but signed with someone else's key — here claiming admin — must
    not authenticate.
    """
    forged = jwt.encode(
        {"sub": "user-123", "role": "admin", "type": "access"},
        "an-attacker-controlled-key",
        algorithm=ALGORITHM,
    )

    assert verify_token(forged, token_type="access") is None


def test_verify_token_rejects_an_expired_token():
    """Expiry is enforced, not merely encoded."""
    expired = create_access_token(USER, expires_delta=timedelta(seconds=-30))

    assert verify_token(expired, token_type="access") is None


def test_verify_token_rejects_a_token_with_no_subject():
    """Without a subject there is no user to act as."""
    anonymous = create_access_token({"email": "student@example.com"})

    assert verify_token(anonymous, token_type="access") is None
