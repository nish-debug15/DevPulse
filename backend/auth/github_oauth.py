import os
import threading
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User
from auth.jwt_handler import (
    create_session_token,
    create_relay_token,
    verify_relay_token,
    RELAY_TOKEN_EXPIRY_SECONDS,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Pre-shared secret that the Next.js /api/auth/exchange route must send as
# X-Exchange-Secret.  This makes /auth/exchange unreachable without the
# secret even while TLS is not yet in place on EC2.
# Set the same value in both backend/.env and Vercel env vars.
EXCHANGE_SECRET = os.getenv("EXCHANGE_SECRET")

# ---------------------------------------------------------------------------
# JTI nonce store — single-use enforcement for relay tokens
# ---------------------------------------------------------------------------
# Maps jti (str) → expires_at (datetime, UTC).
# Thread-safe via _jti_lock; cleaned up lazily on every exchange call.
# Correct for the current single-process uvicorn deployment.
# If you move to multi-worker or multi-instance, replace with Redis or a
# short-TTL SQLite table shared across workers.
_used_jtis: dict[str, datetime] = {}
_jti_lock = threading.Lock()


def _register_jti(jti: str, expires_at: datetime) -> bool:
    """Mark a jti as consumed.  Returns True on first use, False if replayed.

    Also evicts all expired jtis from the store on every call to bound memory.
    """
    now = datetime.now(timezone.utc)
    with _jti_lock:
        # Evict expired entries (lazy GC — bounded by login rate, not time).
        expired = [k for k, exp in _used_jtis.items() if exp <= now]
        for k in expired:
            del _used_jtis[k]

        if jti in _used_jtis:
            return False  # replay detected

        _used_jtis[jti] = expires_at
        return True


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/login")
def github_login():
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}&scope=repo,read:org"
    )
    return RedirectResponse(url=github_auth_url)


@router.get("/callback")
async def github_callback(code: str, db: Session = Depends(get_db)):
    token_url = "https://github.com/login/oauth/access_token"
    headers = {"Accept": "application/json"}
    payload = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
    }

    async with httpx.AsyncClient() as client:
        token_response = await client.post(token_url, json=payload, headers=headers)
        token_data = token_response.json()

        if "error" in token_data:
            raise HTTPException(status_code=400, detail=token_data.get("error_description"))

        access_token = token_data.get("access_token")

        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        user_data = user_response.json()

        github_id = user_data.get("id")
        username = user_data.get("login")
        name = user_data.get("name")

        db_user = db.query(User).filter(User.github_id == github_id).first()

        if db_user:
            db_user.access_token = access_token
            db.commit()
        else:
            db_user = User(
                github_id=github_id,
                username=username,
                name=name,
                access_token=access_token,
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)

        # Issue a short-lived (2 min) relay token for the URL handoff only.
        # The relay token carries a jti claim that /auth/exchange will consume
        # exactly once — a second call with the same token is rejected even
        # within the 2-minute expiry window.
        # The full 7-day session JWT is NEVER placed in a URL.
        relay_token = create_relay_token(db_user.username, db_user.github_id)
        redirect_url = (
            f"{FRONTEND_URL}/api/auth/exchange"
            f"?relay={relay_token}&next=/dashboard/{db_user.username}"
        )
        return RedirectResponse(url=redirect_url)


@router.get("/exchange")
def exchange_relay_token(relay: str, request: Request, db: Session = Depends(get_db)):
    """Exchange a short-lived relay token for a full session token.

    Called server-side only by the Next.js /api/auth/exchange route.

    Security layers:
      1. X-Exchange-Secret header — rejects callers without the pre-shared
         secret so this endpoint is not publicly exploitable while EC2 is
         still on raw HTTP.  (TLS remains the proper fix; this is defence
         in depth.)
      2. type claim — relay tokens and session tokens are cryptographically
         distinct; a session token cannot be presented here.
      3. exp claim — relay tokens expire after 2 minutes.
      4. jti nonce check — each relay token is accepted exactly once;
         a replayed token (e.g. captured from an access log within the
         expiry window) is rejected on second use.
    """
    # --- Layer 1: pre-shared secret (defence-in-depth while TLS is pending) ---
    if EXCHANGE_SECRET:
        provided = request.headers.get("X-Exchange-Secret", "")
        if provided != EXCHANGE_SECRET:
            raise HTTPException(status_code=403, detail="Forbidden")

    # --- Layers 2 & 3: type + expiry ---
    payload = verify_relay_token(relay)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired relay token")

    # --- Layer 4: jti single-use nonce ---
    jti = payload.get("jti")
    if not jti:
        # Relay tokens issued before this commit lack a jti; reject them so
        # old tokens that may still be in logs cannot be used.
        raise HTTPException(status_code=401, detail="Relay token missing nonce (jti)")

    exp_ts = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc)

    if not _register_jti(jti, expires_at):
        raise HTTPException(status_code=401, detail="Relay token already used")

    # All checks passed — issue the real session token.
    username = payload.get("sub")
    db_user = db.query(User).filter(User.username == username).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="User not found")

    session_token = create_session_token(db_user.username, db_user.github_id)
    is_prod = ENVIRONMENT == "production"

    response = JSONResponse(content={"status": "ok", "username": db_user.username})
    response.set_cookie(
        key="devpulse_session",
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=is_prod,
        path="/",
        max_age=7 * 24 * 60 * 60,
    )
    return response