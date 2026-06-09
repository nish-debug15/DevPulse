import os
import json
import logging
from datetime import datetime, timedelta, timezone

from groq import Groq
from sqlalchemy.orm import Session

from db.models import User, PullRequest, Commit
from services.engine import BottleneckEngine

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a senior engineering manager embedded inside a developer analytics tool called DevPulse. "
    "The user will ask you a question about their engineering workflow. "
    "You will be given a JSON context block containing their real pull requests, commits, and performance metrics.\n\n"
    "Rules:\n"
    "1. Answer ONLY based on the provided data context. Never fabricate PR numbers, repo names, or dates.\n"
    "2. If the data doesn't contain enough information to answer, say so explicitly.\n"
    "3. Be direct and concise. Use bullet points for lists.\n"
    "4. Reference specific PR numbers (#N) and repo names when relevant.\n"
    "5. When discussing trends, cite the actual numbers from the context.\n"
    "6. No markdown code fences. Plain text with light formatting only."
)


class QueryEngine:
    _client = None

    @classmethod
    def _get_client(cls) -> Groq:
        if cls._client is None:
            if not os.getenv("GROQ_API_KEY"):
                raise RuntimeError("GROQ_API_KEY environment variable is missing.")
            cls._client = Groq()
        return cls._client

    @staticmethod
    def _build_context(db: Session, user: User) -> dict:
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)

        def ensure_aware(dt: datetime) -> datetime:
            if dt and dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        recent_prs = db.query(PullRequest).filter(
            PullRequest.author_id == user.id,
            PullRequest.created_at >= thirty_days_ago,
        ).order_by(PullRequest.created_at.desc()).limit(50).all()

        recent_commits = db.query(Commit).filter(
            Commit.author_id == user.id,
            Commit.committed_at >= thirty_days_ago,
        ).order_by(Commit.committed_at.desc()).limit(100).all()

        be = BottleneckEngine(db, user)

        return {
            "developer": user.username,
            "snapshot_timestamp": now.isoformat(),
            "pull_requests": [
                {
                    "repo": pr.repo_name,
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "is_merged": pr.is_merged,
                    "created_at": ensure_aware(pr.created_at).isoformat() if pr.created_at else None,
                    "merged_at": ensure_aware(pr.merged_at).isoformat() if pr.merged_at else None,
                }
                for pr in recent_prs
            ],
            "recent_commits": [
                {
                    "repo": c.repo_name,
                    "sha": c.sha[:8],
                    "message": c.message[:120],
                    "committed_at": ensure_aware(c.committed_at).isoformat() if c.committed_at else None,
                }
                for c in recent_commits
            ],
            "metrics": {
                "stale_prs": be.get_stale_prs(),
                "commit_velocity": be.get_commit_velocity(),
                "merge_lag": be.get_merge_lag(),
            },
        }

    @classmethod
    def ask(cls, question: str, db: Session, user: User) -> dict:
        context = cls._build_context(db, user)

        try:
            client = cls._get_client()
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Question: {question}\n\n"
                            f"Data Context:\n{json.dumps(context, indent=2)}"
                        ),
                    },
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.2,
                max_tokens=1024,
            )

            answer = response.choices[0].message.content
            return {
                "status": "success",
                "question": question,
                "answer": answer,
                "context_stats": {
                    "prs_analyzed": len(context["pull_requests"]),
                    "commits_analyzed": len(context["recent_commits"]),
                },
            }

        except Exception as e:
            logger.error(f"Query engine failed: {e}")
            return {
                "status": "error",
                "question": question,
                "answer": "The query engine is temporarily unavailable. Please try again.",
                "context_stats": {},
            }
