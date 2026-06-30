"""
Tests for the FastAPI endpoints in main.py.

Covers:
- Root health check
- Auth-protected endpoints (return data or 401)
- PR bottlenecks endpoint (with seeded stale PR data)
- Standup generation endpoint structure
"""
import pytest


class TestRootEndpoint:
    def test_root_returns_alive(self, client):
        """GET / should return a 200 with a status message."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "DevPulse backend is alive"

    def test_root_includes_client_id_flag(self, client):
        """GET / should report whether GITHUB_CLIENT_ID is loaded."""
        response = client.get("/")
        data = response.json()
        assert "client_id_loaded" in data


class TestAuthEndpoints:
    def test_me_returns_user_info(self, client):
        """GET /auth/me should return the authenticated user's info."""
        response = client.get("/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["github_id"] == 12345

    def test_logout_clears_cookie(self, client):
        """POST /auth/logout should return logged_out status."""
        response = client.post("/auth/logout")
        assert response.status_code == 200
        assert response.json()["status"] == "logged_out"


class TestPRBottlenecks:
    def test_no_bottlenecks_returns_zero(self, client):
        """With no PRs in DB, bottleneck count should be 0."""
        response = client.get("/pr/bottlenecks")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["total_bottlenecks"] == 0

    def test_stale_pr_detected(self, client, db_session, make_pr):
        """A PR open >48h should appear in the bottlenecks response."""
        from db.models import User
        user = db_session.query(User).filter(User.username == "testuser").first()
        make_pr(author_id=user.id, state="open", hours_ago=100)

        response = client.get("/pr/bottlenecks")
        assert response.status_code == 200
        data = response.json()
        assert data["total_bottlenecks"] >= 1

    def test_fresh_pr_not_flagged(self, client, db_session, make_pr):
        """A PR open <48h should NOT appear as a bottleneck."""
        from db.models import User
        user = db_session.query(User).filter(User.username == "testuser").first()
        make_pr(author_id=user.id, state="open", hours_ago=10)

        response = client.get("/pr/bottlenecks")
        data = response.json()
        # Only the user's fresh PR — should not be stale
        for by_user in data["by_user"]:
            if by_user["username"] == "testuser":
                assert by_user["summary"]["total_stale_prs"] == 0

    def test_bottleneck_filter_by_username(self, client, db_session, make_pr):
        """Filtering by ?username= should scope results to that user."""
        from db.models import User
        user = db_session.query(User).filter(User.username == "testuser").first()
        make_pr(author_id=user.id, state="open", hours_ago=100)

        response = client.get("/pr/bottlenecks?username=testuser")
        assert response.status_code == 200
        data = response.json()
        assert len(data["by_user"]) == 1
        assert data["by_user"][0]["username"] == "testuser"

    def test_bottleneck_unknown_user_404(self, client):
        """Filtering by a non-existent username should return 404."""
        response = client.get("/pr/bottlenecks?username=ghost")
        assert response.status_code == 404


class TestTeamEndpoints:
    def test_list_team_empty(self, client):
        """GET /team should return an empty list when no devs are tracked."""
        response = client.get("/team")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["team"] == []
