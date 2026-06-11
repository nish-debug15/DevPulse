import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
if not os.getenv("ENCRYPTION_KEY"):
    raise RuntimeError("CRITICAL STARTUP FAILURE: ENCRYPTION_KEY is missing from .env.")
if not os.getenv("GROQ_API_KEY"):
    raise RuntimeError("CRITICAL STARTUP FAILURE: GROQ_API_KEY is missing from .env.")

from typing import Optional
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from db.database import get_db, engine, Base
from db.models import User, TrackedDeveloper
from services.github_fetcher import sync_user_github_data, sync_tracked_developer
from auth.github_oauth import router as auth_router

from services.engine import BottleneckEngine
from services.ai_synthesis import StandupGenerator
from services.slack_notifier import SlackNotifier
from services.query_engine import QueryEngine
from auth.dependencies import get_authenticated_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)
scheduler = AsyncIOScheduler()

async def scheduled_github_sync():
    """Background job to iterate over all users and sync their data."""
    logger.info("Starting hourly GitHub data sync for all users...")
    
    def get_user_ids():
        with Session(engine) as db:
            return [u.id for u in db.query(User).filter(User.access_token.isnot(None)).all()]
            
    try:
        user_ids = await asyncio.to_thread(get_user_ids)
        
        for uid in user_ids:
            with Session(engine) as db:
                user = db.query(User).get(uid)
                if user:
                    try:
                        await sync_user_github_data(user, db)
                        logger.info(f"Successfully synced data for {user.username}")
                    except Exception as e:
                        logger.error(f"Failed to sync user {user.username}: {e}")

                    tracked = db.query(TrackedDeveloper).filter(TrackedDeveloper.manager_id == user.id).all()
                    for td in tracked:
                        try:
                            await sync_tracked_developer(td.developer.username, user, td.developer, db)
                            logger.info(f"Synced tracked dev {td.developer.username} for manager {user.username}")
                        except Exception as e:
                            logger.error(f"Failed to sync tracked dev {td.developer.username}: {e}")
    except Exception as e:
        logger.error(f"Critical failure in scheduled sync: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

@app.get("/")
def read_root():
    return {"status": "DevPulse backend is alive", "client_id_loaded": bool(os.getenv("GITHUB_CLIENT_ID"))}


@app.get("/auth/me")
def get_current_user(user: User = Depends(get_authenticated_user)):
    return {"username": user.username, "name": user.name, "github_id": user.github_id}


@app.post("/auth/logout")
def logout():
    response = JSONResponse(content={"status": "logged_out"})
    response.delete_cookie(key="devpulse_session", path="/")
    return response

@app.post("/users/{username}/sync")
def manual_github_sync(
    username: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
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
def get_daily_standup(
    username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
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


def _classify_severity(hours_open: float) -> str:
    """Classify a stale PR's severity based on how long it has been open."""
    if hours_open > 168:
        return "critical"
    elif hours_open > 72:
        return "warning"
    return "stale"


def _build_user_bottleneck(db: Session, user: User) -> dict:
    """Build the bottleneck payload for a single user using BottleneckEngine."""
    be = BottleneckEngine(db, user)
    stale_prs = be.get_stale_prs()
    commit_velocity = be.get_commit_velocity()
    merge_lag = be.get_merge_lag()

    critical_count = 0
    warning_count = 0
    stale_count = 0
    bottlenecks_by_repo: dict[str, list] = {}

    for pr in stale_prs:
        severity = _classify_severity(pr["hours_open"])
        if severity == "critical":
            critical_count += 1
        elif severity == "warning":
            warning_count += 1
        else:
            stale_count += 1

        repo = pr["repo"]
        bottlenecks_by_repo.setdefault(repo, []).append({
            "number": pr["number"],
            "title": pr["title"],
            "hours_open": pr["hours_open"],
            "severity": severity,
        })

    return {
        "username": user.username,
        "summary": {
            "total_stale_prs": len(stale_prs),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "stale_count": stale_count,
            "commit_velocity": commit_velocity,
            "merge_lag": merge_lag,
        },
        "bottlenecks_by_repo": bottlenecks_by_repo,
    }


@app.get("/pr/bottlenecks")
def get_pr_bottlenecks(
    username: Optional[str] = Query(None, description="Filter bottlenecks for a specific GitHub username"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Returns PR bottleneck data grouped by user and repo with severity classification."""
    if username:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found")
        users = [user]
    else:
        users = db.query(User).all()

    by_user = []
    total_bottlenecks = 0

    for user in users:
        payload = _build_user_bottleneck(db, user)
        total_bottlenecks += payload["summary"]["total_stale_prs"]
        by_user.append(payload)

    return {
        "status": "success",
        "total_bottlenecks": total_bottlenecks,
        "by_user": by_user,
    }


@app.post("/slack/send")
def send_slack_notification(
    request_body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    username = request_body.get("username")
    msg_type = request_body.get("type", "standup")

    if not username:
        raise HTTPException(status_code=400, detail="'username' is required")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")

    if msg_type == "standup":
        be = BottleneckEngine(db, user)
        metrics = be.generate_metrics_payload()
        standup_text = StandupGenerator.generate(metrics)
        sent = SlackNotifier.send_standup(username, standup_text)
    elif msg_type == "bottleneck":
        payload = _build_user_bottleneck(db, user)
        sent = SlackNotifier.send_bottleneck_alert(username, payload)
    else:
        raise HTTPException(status_code=400, detail="'type' must be 'standup' or 'bottleneck'")

    return {
        "status": "sent" if sent else "skipped",
        "message": "Notification delivered to Slack" if sent else "SLACK_WEBHOOK_URL not configured",
    }


@app.post("/query")
def natural_language_query(
    request_body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    question = request_body.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="'question' is required")

    return QueryEngine.ask(question, db, current_user)


@app.post("/team/add")
async def add_tracked_developer(
    request_body: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    github_username = request_body.get("github_username", "").strip().lower()
    if not github_username:
        raise HTTPException(status_code=400, detail="'github_username' is required")

    if github_username == current_user.username:
        raise HTTPException(status_code=400, detail="You are already tracking yourself")

    import httpx
    headers = {
        "Authorization": f"Bearer {current_user.access_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
        res = await client.get(f"https://api.github.com/users/{github_username}")
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"GitHub user '{github_username}' does not exist")
        if res.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to verify user on GitHub")
        gh_data = res.json()

    shadow_user = db.query(User).filter(User.username == github_username).first()
    if not shadow_user:
        shadow_user = User(
            github_id=gh_data["id"],
            username=github_username,
            name=gh_data.get("name"),
            access_token=None,
        )
        db.add(shadow_user)
        db.commit()
        db.refresh(shadow_user)

    existing = db.query(TrackedDeveloper).filter(
        TrackedDeveloper.manager_id == current_user.id,
        TrackedDeveloper.developer_id == shadow_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Already tracking '{github_username}'")

    td = TrackedDeveloper(manager_id=current_user.id, developer_id=shadow_user.id)
    db.add(td)
    db.commit()

    background_tasks.add_task(sync_tracked_developer, github_username, current_user, shadow_user, db)

    return {
        "status": "added",
        "developer": {
            "username": shadow_user.username,
            "name": shadow_user.name,
            "github_id": shadow_user.github_id,
        },
    }


@app.get("/team")
def list_tracked_developers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    tracked = db.query(TrackedDeveloper).filter(
        TrackedDeveloper.manager_id == current_user.id
    ).all()

    developers = []
    for td in tracked:
        dev = td.developer
        developers.append({
            "username": dev.username,
            "name": dev.name,
            "github_id": dev.github_id,
            "last_synced_at": dev.last_synced_at.isoformat() if dev.last_synced_at else None,
            "added_at": td.added_at.isoformat() if td.added_at else None,
        })

    return {"status": "success", "team": developers}


@app.delete("/team/{github_username}")
def remove_tracked_developer(
    github_username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    shadow_user = db.query(User).filter(User.username == github_username).first()
    if not shadow_user:
        raise HTTPException(status_code=404, detail=f"Developer '{github_username}' not found")

    td = db.query(TrackedDeveloper).filter(
        TrackedDeveloper.manager_id == current_user.id,
        TrackedDeveloper.developer_id == shadow_user.id,
    ).first()
    if not td:
        raise HTTPException(status_code=404, detail=f"You are not tracking '{github_username}'")

    db.delete(td)
    db.commit()

    return {"status": "removed", "username": github_username}


@app.post("/team/{github_username}/sync")
async def sync_single_tracked_developer(
    github_username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    shadow_user = db.query(User).filter(User.username == github_username).first()
    if not shadow_user:
        raise HTTPException(status_code=404, detail=f"Developer '{github_username}' not found")

    td = db.query(TrackedDeveloper).filter(
        TrackedDeveloper.manager_id == current_user.id,
        TrackedDeveloper.developer_id == shadow_user.id,
    ).first()
    if not td:
        raise HTTPException(status_code=404, detail=f"You are not tracking '{github_username}'")

    await sync_tracked_developer(github_username, current_user, shadow_user, db)

    return {"status": "synced", "username": github_username}