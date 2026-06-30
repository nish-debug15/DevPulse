import asyncio
import httpx
import logging
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert
from fastapi import HTTPException

from db.models import User, PullRequest, Commit

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 2


def parse_gh_date(date_str: str):
    if not date_str:
        return None
    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))


async def _wait_for_rate_limit_reset(response: httpx.Response) -> None:
    """Sleep until the GitHub rate limit resets, based on response headers."""
    reset_timestamp = response.headers.get("X-RateLimit-Reset")
    if reset_timestamp:
        wait_seconds = max(int(reset_timestamp) - int(time.time()), 1) + 1
        # Cap the wait to 15 minutes to avoid infinite hangs
        wait_seconds = min(wait_seconds, 900)
        logger.warning(f"Rate limit hit. Sleeping for {wait_seconds}s until reset.")
        await asyncio.sleep(wait_seconds)
    else:
        # Fallback: if no reset header, wait 60s
        logger.warning("Rate limit hit but no reset header found. Sleeping 60s.")
        await asyncio.sleep(60)


async def fetch_with_retry(client: httpx.AsyncClient, url: str) -> list:
    """
    Paginated GitHub API fetcher with:
    - Rate-limit awareness: sleeps until X-RateLimit-Reset on 403/429.
    - Exponential backoff: retries transient 5xx errors up to MAX_RETRIES.
    - Pagination cap: stops after 500 items to avoid runaway syncs.
    """
    results = []
    current_url = url

    while current_url:
        retries = 0
        response = None

        while retries <= MAX_RETRIES:
            response = await client.get(current_url)

            # --- Rate Limit Handling (403 or 429) ---
            if response.status_code in (403, 429):
                remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
                if remaining == 0 or response.status_code == 429:
                    await _wait_for_rate_limit_reset(response)
                    retries += 1
                    continue
                # 403 for non-rate-limit reasons (e.g. repo access denied)
                logger.error(f"GitHub 403 (not rate limit): {response.text[:200]}")
                return results

            # --- Transient Server Errors (5xx) ---
            if response.status_code >= 500:
                retries += 1
                wait = BACKOFF_BASE_SECONDS ** retries
                logger.warning(
                    f"GitHub {response.status_code} error. Retry {retries}/{MAX_RETRIES} in {wait}s."
                )
                await asyncio.sleep(wait)
                continue

            # --- Other Client Errors (4xx) ---
            if response.status_code != 200:
                logger.error(f"GitHub API Error {response.status_code}: {response.text[:200]}")
                return results

            # --- Success ---
            break
        else:
            # Exhausted all retries
            logger.error(f"Exhausted {MAX_RETRIES} retries for {current_url}. Skipping.")
            return results

        # Log low rate-limit headroom as a warning
        remaining = int(response.headers.get("X-RateLimit-Remaining", 100))
        if remaining < 50:
            logger.warning(f"Rate limit headroom low: {remaining} requests remaining.")

        results.extend(response.json())

        current_url = response.links.get("next", {}).get("url")

        if len(results) >= 500:
            break

    return results

async def sync_user_github_data(user: User, db: Session):
    if not user.access_token:
        logger.error(f"User {user.username} has no access token. Skipping sync.")
        return 

    headers = {
        "Authorization": f"Bearer {user.access_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
        repos_url = "https://api.github.com/user/repos?sort=updated&per_page=5"
        repos = await fetch_with_retry(client, repos_url)

        for repo in repos:
            repo_name = repo["full_name"]
            
            pr_url = f"https://api.github.com/repos/{repo_name}/pulls?state=all&per_page=50"
            prs_data = await fetch_with_retry(client, pr_url)
            if prs_data:
                upsert_prs(db, user.id, repo_name, prs_data)

            commits_url = f"https://api.github.com/repos/{repo_name}/commits?author={user.username}&per_page=50"
            commits_data = await fetch_with_retry(client, commits_url)
            if commits_data:
                upsert_commits(db, user.id, repo_name, commits_data)

    user.last_synced_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()


async def sync_tracked_developer(target_username: str, manager: User, shadow_user: User, db: Session):
    if not manager.access_token:
        logger.error(f"Manager {manager.username} has no access token. Cannot sync tracked dev.")
        return

    headers = {
        "Authorization": f"Bearer {manager.access_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
        repos_url = f"https://api.github.com/users/{target_username}/repos?sort=updated&per_page=10"
        repos = await fetch_with_retry(client, repos_url)

        for repo in repos:
            repo_name = repo["full_name"]

            pr_url = f"https://api.github.com/repos/{repo_name}/pulls?state=all&per_page=50"
            prs_data = await fetch_with_retry(client, pr_url)
            if prs_data:
                user_prs = [pr for pr in prs_data if pr.get("user", {}).get("login") == target_username]
                if user_prs:
                    upsert_prs(db, shadow_user.id, repo_name, user_prs)

            commits_url = f"https://api.github.com/repos/{repo_name}/commits?author={target_username}&per_page=50"
            commits_data = await fetch_with_retry(client, commits_url)
            if commits_data:
                upsert_commits(db, shadow_user.id, repo_name, commits_data)

    shadow_user.last_synced_at = datetime.now(timezone.utc)
    db.add(shadow_user)
    db.commit()


def upsert_prs(db: Session, user_id: int, repo_name: str, prs_data: list):
    for pr in prs_data:
        stmt = insert(PullRequest).values(
            github_pr_id=pr["id"],
            repo_name=repo_name,
            number=pr["number"],
            title=pr["title"],
            state=pr["state"],
            is_merged=bool(pr.get("merged_at")),
            created_at=parse_gh_date(pr.get("created_at")),
            updated_at=parse_gh_date(pr.get("updated_at")),
            merged_at=parse_gh_date(pr.get("merged_at")),
            author_id=user_id
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["github_pr_id"],
            set_={
                "state": stmt.excluded.state,
                "is_merged": stmt.excluded.is_merged,
                "updated_at": stmt.excluded.updated_at,
                "merged_at": stmt.excluded.merged_at
            }
        )
        db.execute(stmt)
    db.commit()

def upsert_commits(db: Session, user_id: int, repo_name: str, commits_data: list):
    for item in commits_data:
        commit_info = item.get("commit", {})
        author_info = commit_info.get("author", {})
        
        stmt = insert(Commit).values(
            sha=item["sha"],
            repo_name=repo_name,
            message=commit_info.get("message", "")[:255],
            committed_at=parse_gh_date(author_info.get("date")),
            author_id=user_id
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["sha"])
        db.execute(stmt)
    db.commit()