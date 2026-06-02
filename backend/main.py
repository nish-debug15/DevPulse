from fastapi import FastAPI
import os
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import User
from services.github_fetcher import sync_user_github_data

from db.database import engine, Base
import db.models 

from auth.github_oauth import router as auth_router

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="DevPulse API")
app.include_router(auth_router)

@app.get("/")
def read_root():
    return {"status": "DevPulse backend is alive", "client_id_loaded": bool(os.getenv("GITHUB_CLIENT_ID"))}

@app.post("/users/{username}/sync")
async def manual_github_sync(username: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Manually triggers the GitHub data sync for a specific user."""
    user = db.query(User).filter(User.username == username).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found in database")
    
    background_tasks.add_task(sync_user_github_data, user, db)
    
    return {
        "status": "Sync initiated", 
        "message": f"Fetching PRs and commits for {username} in the background."
    }