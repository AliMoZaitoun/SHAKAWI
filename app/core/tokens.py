"""Short-lived JWT access tokens for employee API clients."""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

ACCESS_TOKEN_TTL_SECONDS = 15 * 60
_ISSUER = "shakwa"
_AUDIENCE = "shakwa-staff-api"
_KEY_LABEL = b"shakwa:employee-access-token:v1"


def _signing_key() -> bytes:
    session_secret = os.environ.get("SESSION_SECRET")
    if not session_secret:
        raise RuntimeError("SESSION_SECRET must be configured before issuing access tokens")
    # Domain separation avoids reusing the session-signing key directly and
    # does not require another secret to be copied into local .env files.
    return hmac.new(session_secret.encode("utf-8"), _KEY_LABEL, hashlib.sha256).digest()


def create_access_token(employee) -> dict:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS)
    token = jwt.encode(
        {
            "sub": str(employee.id),
            "pwdv": employee.password_version,
            "iat": issued_at,
            "exp": expires_at,
            "iss": _ISSUER,
            "aud": _AUDIENCE,
        },
        _signing_key(),
        algorithm="HS256",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_TTL_SECONDS,
    }


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        _signing_key(),
        algorithms=["HS256"],
        issuer=_ISSUER,
        audience=_AUDIENCE,
        options={"require": ["exp", "iat", "sub", "pwdv"]},
        leeway=5,
    )
