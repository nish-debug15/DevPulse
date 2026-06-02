from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from typing import Dict, Any

from db.models import User, PullRequest, Commit

class BottleneckEngine:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.now = datetime.now(timezone.utc)

    def get_stale_prs(self) -> list[Dict[str, Any]]:
        """Finds PRs open for more than 48 hours."""
        threshold = self.now - timedelta(hours=48)
        
        stale_prs = self.db.query(PullRequest).filter(
            PullRequest.author_id == self.user.id,
            PullRequest.state == "open",
            PullRequest.created_at <= threshold
        ).all()
        
        results = []
        for pr in stale_prs:
            hours_open = round((self.now - pr.created_at).total_seconds() / 3600, 1)
            results.append({
                "repo": pr.repo_name,
                "number": pr.number,
                "title": pr.title,
                "hours_open": hours_open
            })
            
        return results

    def get_commit_velocity(self) -> Dict[str, int]:
        """Compares commit volume in the last 7 days vs the previous 7 days."""
        seven_days_ago = self.now - timedelta(days=7)
        fourteen_days_ago = self.now - timedelta(days=14)

        current_week_commits = self.db.query(Commit).filter(
            Commit.author_id == self.user.id,
            Commit.committed_at >= seven_days_ago
        ).count()

        previous_week_commits = self.db.query(Commit).filter(
            Commit.author_id == self.user.id,
            Commit.committed_at >= fourteen_days_ago,
            Commit.committed_at < seven_days_ago
        ).count()

        return {
            "current_week": current_week_commits,
            "previous_week": previous_week_commits,
            "trend": current_week_commits - previous_week_commits
        }

    def get_merge_lag(self) -> Dict[str, Any]:
        """Calculates average hours from PR creation to merge over the last 30 days."""
        thirty_days_ago = self.now - timedelta(days=30)
        
        merged_prs = self.db.query(PullRequest).filter(
            PullRequest.author_id == self.user.id,
            PullRequest.is_merged == True,
            PullRequest.merged_at >= thirty_days_ago
        ).all()

        if not merged_prs:
            return {"average_hours": 0, "pr_count": 0}

        total_seconds = sum(
            (pr.merged_at - pr.created_at).total_seconds() 
            for pr in merged_prs 
            if pr.merged_at and pr.created_at
        )
        
        avg_hours = (total_seconds / len(merged_prs)) / 3600

        return {
            "average_hours": round(avg_hours, 1),
            "pr_count": len(merged_prs)
        }

    def generate_metrics_payload(self) -> Dict[str, Any]:
        """Aggregates all metrics into a single payload for the LLM context window."""
        return {
            "developer": self.user.username,
            "timestamp": self.now.isoformat(),
            "stale_prs": self.get_stale_prs(),
            "commit_velocity": self.get_commit_velocity(),
            "merge_lag": self.get_merge_lag()
        }