import os
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

@router.get("/login")
def github_login():
    """Redirects the user to GitHub's OAuth consent screen."""
    github_auth_url = f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&scope=repo,read:org"
    return RedirectResponse(url=github_auth_url)

@router.get("/callback")
async def github_callback(code: str):
    """GitHub redirects here with a temporary code. We exchange it for an access token."""
    
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

        repos_url = "https://api.github.com/user/repos?sort=updated&per_page=5"
        repos_response = await client.get(repos_url, headers=user_headers)
        repos_data = repos_response.json()

        print(f"\n--- RECENT REPOS FOR {user_data.get('login').upper()} ---")
        for repo in repos_data:
            print(f"- {repo.get('name')} (Private: {repo.get('private')})")
        print("---------------------------------------\n")

        return {
            "message": "Authentication successful!",
            "github_username": user_data.get("login"),
            "name": user_data.get("name"),
            "status": "Check your VS Code terminal to see your fetched repos!"
        }