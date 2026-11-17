"""Core security utilities for bcrypt password hashing, JWT tokens, and rate limiting."""

from datetime import datetime, timedelta, timezone
import types
from typing import Any, Dict, Optional

import bcrypt
from jose import jwt
from passlib.context import CryptContext
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.core.config import get_settings

# Ensure passlib 1.7.4 works cleanly with modern bcrypt >= 4.1 / 5.x without warnings or 72-byte wrap-check errors
if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = types.SimpleNamespace(  # type: ignore[attr-defined]
        __version__=getattr(bcrypt, "__version__", "4.0.0")
    )

_orig_bcrypt_hashpw = bcrypt.hashpw


def _safe_bcrypt_hashpw(password: bytes | str, salt: bytes) -> bytes:
    raw_bytes = (
         bytes(password)
        if isinstance(password, (bytes, bytearray))
        else str(password).encode("utf-8")
    )
    return _orig_bcrypt_hashpw(raw_bytes[:72], salt)


bcrypt.hashpw = _safe_bcrypt_hashpw  # type: ignore[assignment]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Shared SlowAPI rate limiter instance keyed by client remote IP address
limiter = Limiter(key_func=get_remote_address)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


hash_password = get_password_hash


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed HS256 JWT access token with an expiration timestamp."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
