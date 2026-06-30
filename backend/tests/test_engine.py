"""
Tests for the BottleneckEngine service.

Covers:
- Stale PR detection (open > 48h)
- Commit velocity comparison (current vs previous week)
- Merge lag calculation
- Full metrics payload generation
"""
import pytest
from datetime import datetime, timedelta, timezone

from services.engine import BottleneckEngine


class TestStalePRDetection:
    def test_old_open_pr_is_stale(self, db_session, make_user, make_pr):
        """A PR open for >48 hours should be flagged as stale."""
        user = make_user(username="stale_tester", github_id=200)
        make_pr(author_id=user.id, state="open", hours_ago=96)

        engine = BottleneckEngine(db_session, user)
        stale = engine.get_stale_prs()
        assert len(stale) == 1
        assert stale[0]["hours_open"] >= 96

    def test_fresh_open_pr_not_stale(self, db_session, make_user, make_pr):
        """A PR open for <48 hours should NOT be flagged."""
        user = make_user(username="fresh_tester", github_id=201)
        make_pr(author_id=user.id, state="open", hours_ago=10)

        engine = BottleneckEngine(db_session, user)
        stale = engine.get_stale_prs()
        assert len(stale) == 0

    def test_closed_pr_not_stale(self, db_session, make_user, make_pr):
        """A closed PR — even if old — should NOT appear as stale."""
        user = make_user(username="closed_tester", github_id=202)
        make_pr(author_id=user.id, state="closed", hours_ago=200)

        engine = BottleneckEngine(db_session, user)
        stale = engine.get_stale_prs()
        assert len(stale) == 0


class TestCommitVelocity:
    def test_velocity_with_commits(self, db_session, make_user, make_commit):
        """Should correctly count commits from current vs previous week."""
        user = make_user(username="velocity_user", github_id=300)
        # 3 commits in current week (days_ago=1,2,3)
        for d in [1, 2, 3]:
            make_commit(author_id=user.id, days_ago=d)
        # 1 commit in previous week (days_ago=10)
        make_commit(author_id=user.id, days_ago=10)

        engine = BottleneckEngine(db_session, user)
        velocity = engine.get_commit_velocity()

        assert velocity["current_week"] == 3
        assert velocity["previous_week"] == 1
        assert velocity["trend"] == 2

    def test_velocity_zero_commits(self, db_session, make_user):
        """With no commits, both weeks should be 0."""
        user = make_user(username="zero_velocity", github_id=301)
        engine = BottleneckEngine(db_session, user)
        velocity = engine.get_commit_velocity()
        assert velocity["current_week"] == 0
        assert velocity["previous_week"] == 0
        assert velocity["trend"] == 0


class TestMergeLag:
    def test_merge_lag_calculation(self, db_session, make_user, make_pr):
        """Should calculate average hours from creation to merge."""
        user = make_user(username="lag_user", github_id=400)
        # A PR created 24h ago and merged now => ~24h lag
        make_pr(author_id=user.id, state="closed", hours_ago=24, merged=True)

        engine = BottleneckEngine(db_session, user)
        lag = engine.get_merge_lag()
        assert lag["pr_count"] == 1
        assert lag["average_hours"] >= 20  # Allow some tolerance

    def test_merge_lag_no_merged_prs(self, db_session, make_user):
        """With no merged PRs, lag should be 0."""
        user = make_user(username="nolag_user", github_id=401)
        engine = BottleneckEngine(db_session, user)
        lag = engine.get_merge_lag()
        assert lag["average_hours"] == 0
        assert lag["pr_count"] == 0


class TestMetricsPayload:
    def test_payload_structure(self, db_session, make_user):
        """generate_metrics_payload should return all expected keys."""
        user = make_user(username="payload_user", github_id=500)
        engine = BottleneckEngine(db_session, user)
        payload = engine.generate_metrics_payload()

        assert payload["developer"] == "payload_user"
        assert "timestamp" in payload
        assert "stale_prs" in payload
        assert "commit_velocity" in payload
        assert "merge_lag" in payload
