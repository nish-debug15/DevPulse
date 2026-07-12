import os
import jwt
from datetime import datetime, timedelta, timezone

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("CRITICAL STARTUP FAILURE: JWT_SECRET is missing from .env.")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7
RELAY_TOKEN_EXPIRY_SECONDS = 120  # 2-minute one-time relay token


def create_session_token(username: str, github_id: int) -> str:
    payload = {
        "sub": username,
        "gid": github_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_session_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def create_relay_token(username: str, github_id: int) -> str:
    """Short-lived (2 min), typed relay token for the OAuth → frontend handoff.

    This token is placed in the redirect URL query string and exchanged
    immediately by the Next.js /api/auth/exchange route for a full session
    token that is set as an httpOnly cookie.  It MUST NOT be used as a
    session credential — verify_relay_token() enforces the type claim.
    """
    payload = {
        "sub": username,
        "gid": github_id,
        "type": "relay",
        "exp": datetime.now(timezone.utc) + timedelta(seconds=RELAY_TOKEN_EXPIRY_SECONDS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_relay_token(token: str) -> dict | None:
    """Validate a relay token.  Returns the payload only if the type claim
    is exactly 'relay', so a full session token cannot be used here."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "relay":
            return None
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
