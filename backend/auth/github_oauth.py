import os
import httpx
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000") # Add this

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

        user_url = "https://api.github.com/user"
        user_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        user_response = await client.get(user_url, headers=user_headers)
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
                access_token=access_token
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)

        return RedirectResponse(url=f"{FRONTEND_URL}/dashboard?user={db_user.username}")