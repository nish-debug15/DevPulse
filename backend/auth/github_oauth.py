import os
import httpx
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User
from auth.jwt_handler import create_session_token, create_relay_token, verify_relay_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


@router.get("/login")
def github_login():
    github_auth_url = f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&scope=repo,read:org"
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
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github.v3+json"},
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
            db_user = User(github_id=github_id, username=username, name=name, access_token=access_token)
            db.add(db_user)
            db.commit()
            db.refresh(db_user)

        # Issue a short-lived (2 min) relay token for the URL handoff only.
        # The full session token is NEVER placed in a URL — it is issued by
        # /auth/exchange after the relay token is validated server-side and
        # set as an httpOnly cookie on the frontend origin by the Next.js
        # API route /api/auth/exchange.
        relay_token = create_relay_token(db_user.username, db_user.github_id)
        redirect_url = f"{FRONTEND_URL}/api/auth/exchange?relay={relay_token}&next=/dashboard/{db_user.username}"
        return RedirectResponse(url=redirect_url)


@router.get("/exchange")
def exchange_relay_token(relay: str, db: Session = Depends(get_db)):
    """Exchange a short-lived relay token for a full session token.

    Called server-side by the Next.js /api/auth/exchange route.
    Returns a JSON response with Set-Cookie bearing the real session token.
    The relay token is validated for type ('relay') and expiry; a full
    session token cannot be used here due to the type claim check.
    """
    payload = verify_relay_token(relay)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired relay token")

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