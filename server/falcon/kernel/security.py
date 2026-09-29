"""Security primitives.

* Passwords: Argon2id (RFC 9106 second recommended profile, 64 MiB, t=3).
* Opaque secrets (session ids, activation links, access tokens): 256 bits from
  the OS CSPRNG, stored only as SHA-256 digests, so a database leak does not
  yield usable credentials.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4)

# A syntactically valid hash used to equalise timing when the account is unknown.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))

PASSWORD_MIN_LENGTH = 12
TOKEN_PREFIX = "flc_"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, stored_hash: str | None) -> bool:
    """Constant-work verification; unknown accounts still pay the Argon2 cost."""
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


def password_problems(password: str, *, email: str | None = None, name: str | None = None) -> list[str]:
    """Human-readable reasons a password is rejected (empty when acceptable)."""
    problems: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(f"Use at least {PASSWORD_MIN_LENGTH} characters")
    if len(password) > 256:
        problems.append("Use at most 256 characters")
    classes = sum(
        (
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        )
    )
    if classes < 3:
        problems.append("Mix at least three of: lowercase, uppercase, digits, symbols")
    lowered = password.lower()
    if email and email.split("@")[0].lower() in lowered and len(email.split("@")[0]) >= 3:
        problems.append("Do not include your email name")
    if name and any(part.lower() in lowered for part in name.split() if len(part) >= 3):
        problems.append("Do not include your name")
    return problems


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def new_access_token() -> tuple[str, str]:
    """Returns (plaintext, display prefix). The plaintext is shown exactly once."""
    plaintext = TOKEN_PREFIX + secrets.token_urlsafe(32)
    return plaintext, plaintext[:12]


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
