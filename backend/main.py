import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException
import logging
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from db.database import get_db, engine, Base
from db.models import User
from services.github_fetcher import sync_user_github_data
from auth.github_oauth import router as auth_router

from services.engine import BottleneckEngine
from services.ai_synthesis import StandupGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

scheduler = AsyncIOScheduler()

async def scheduled_github_sync():
    """Background job to iterate over all users and sync their data."""
    logger.info("Starting hourly GitHub data sync for all users...")
    
    with Session(engine) as db:
        users = db.query(User).all()
        for user in users:
            try:
                await sync_user_github_data(user, db)
                logger.info(f"Successfully synced data for {user.username}")
            except Exception as e:
                logger.error(f"Failed to sync user {user.username}: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern FastAPI pattern for handling startup and shutdown events."""
    scheduler.add_job(
        scheduled_github_sync, 
        'interval', 
        hours=1, 
        id='hourly_github_sync', 
        replace_existing=True
    )
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="DevPulse API", lifespan=lifespan)
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

@app.get("/users/{username}/standup")
def get_daily_standup(username: str, db: Session = Depends(get_db)):
    """Generates the AI-powered standup for a specific user."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        engine = BottleneckEngine(db, user)
        metrics = engine.generate_metrics_payload()

        standup_text = StandupGenerator.generate(metrics)

        return {
            "status": "success",
            "username": username,
            "metrics_snapshot": metrics,
            "standup_summary": standup_text
        }
    except Exception as e:
        logger.error(f"Error generating standup for {username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate the AI standup.")