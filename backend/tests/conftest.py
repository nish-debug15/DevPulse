"""
Shared test fixtures for the DevPulse test suite.

Provides:
- An in-memory SQLite database and session (no disk I/O).
- A FastAPI TestClient with auth dependency overridden (no real OAuth needed).
- Factory helpers for creating test users, PRs, and commits.
"""
import os
import sys

# CRITICAL: Generate a valid Fernet key and set env vars BEFORE any app imports.
# models.py reads ENCRYPTION_KEY at module load time, so this must come first.
from cryptography.fernet import Fernet

_test_fernet_key = Fernet.generate_key().decode()
os.environ["ENCRYPTION_KEY"] = _test_fernet_key
os.environ.setdefault("GROQ_API_KEY", "fake-groq-key-for-testing")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import Base, get_db
from db.models import User, PullRequest, Commit


from sqlalchemy.pool import StaticPool


# ─── Database fixtures ───────────────────────────────────────────────

@pytest.fixture()
def db_session():
    """Creates a fresh in-memory SQLite database for each test.
    Uses StaticPool so all connections share the same in-memory DB."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    """
    FastAPI TestClient with the DB dependency overridden to use the
    in-memory session, and the auth dependency overridden to return
    a test user (bypassing real OAuth).
    """
    from fastapi.testclient import TestClient
    from main import app
    from auth.dependencies import get_authenticated_user

    # Seed a test user
    test_user = User(
        github_id=12345,
        username="testuser",
        name="Test User",
        access_token="fake-token",
    )
    db_session.add(test_user)
    db_session.commit()
    db_session.refresh(test_user)

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass  # Don't close — the db_session fixture manages lifecycle

    def _override_auth():
        return test_user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_authenticated_user] = _override_auth

    # raise_server_exceptions=True (default) to get proper test failure messages
    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ─── Factory helpers ─────────────────────────────────────────────────

@pytest.fixture()
def make_user(db_session):
    """Factory to create a User row quickly."""
    def _make(username="devuser", github_id=99, access_token="tok-abc"):
        user = User(github_id=github_id, username=username, name=username.title(), access_token=access_token)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    return _make


@pytest.fixture()
def make_pr(db_session):
    """Factory to create a PullRequest row quickly."""
    _counter = [0]

    def _make(author_id, repo="org/repo", state="open", hours_ago=72, merged=False):
        _counter[0] += 1
        now = datetime.now(timezone.utc)
        pr = PullRequest(
            github_pr_id=1000 + _counter[0],
            repo_name=repo,
            number=_counter[0],
            title=f"Test PR #{_counter[0]}",
            state=state,
            is_merged=merged,
            created_at=now - timedelta(hours=hours_ago),
            updated_at=now - timedelta(hours=1),
            merged_at=now if merged else None,
            author_id=author_id,
        )
        db_session.add(pr)
        db_session.commit()
        return pr
    return _make


@pytest.fixture()
def make_commit(db_session):
    """Factory to create a Commit row quickly."""
    _counter = [0]

    def _make(author_id, repo="org/repo", days_ago=1):
        _counter[0] += 1
        now = datetime.now(timezone.utc)
        c = Commit(
            sha=f"abc{_counter[0]:06d}",
            repo_name=repo,
            message=f"commit message {_counter[0]}",
            committed_at=now - timedelta(days=days_ago),
            author_id=author_id,
        )
        db_session.add(c)
        db_session.commit()
        return c
    return _make
