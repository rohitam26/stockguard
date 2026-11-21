import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
from stockguard.config import get_settings

settings = get_settings()


def create_access_token(
    subject: str,
    role: str,
    email: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, int]:
    """
    Creates a cryptographically signed JWT access token.
    Returns (token_string, expires_in_seconds).
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    expires_in = int((expire - now).total_seconds())

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "email": email,
        "role": str(role),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt, expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodes and validates a JWT access token.
    Raises jwt.PyJWTError on invalid signature, expiration, or format.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["sub", "exp", "iat"]},
    )


def generate_refresh_token() -> str:
    """Generate an opaque high-entropy refresh token string."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Hash token using SHA-256 for secure storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
