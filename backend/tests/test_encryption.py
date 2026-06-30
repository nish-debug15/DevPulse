"""
Tests for the EncryptedString TypeDecorator and Fernet token security.

Proves that:
- Tokens are encrypted before being written to the database.
- Tokens are decrypted transparently when read back via SQLAlchemy.
- Raw DB values are NOT plaintext (i.e., an attacker with DB access sees ciphertext).
"""
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from db.database import Base
from db.models import User


class TestEncryptedTokenStorage:
    def test_token_roundtrip(self, db_session):
        """Storing and reading a token via the ORM should return the original value."""
        user = User(
            github_id=42,
            username="crypto_test",
            name="Crypto Tester",
            access_token="ghp_super_secret_token_12345",
        )
        db_session.add(user)
        db_session.commit()

        fetched = db_session.query(User).filter(User.username == "crypto_test").first()
        assert fetched.access_token == "ghp_super_secret_token_12345"

    def test_raw_db_value_is_encrypted(self, db_session):
        """
        The raw value stored in SQLite must NOT be the plaintext token.
        This is the critical security assertion.
        """
        plaintext = "ghp_this_must_not_appear_in_db"
        user = User(
            github_id=43,
            username="raw_check",
            name="Raw Checker",
            access_token=plaintext,
        )
        db_session.add(user)
        db_session.commit()

        # Bypass SQLAlchemy ORM — read the raw column value with a text query.
        result = db_session.execute(
            text("SELECT access_token FROM users WHERE username = 'raw_check'")
        )
        raw_value = result.scalar()

        assert raw_value is not None
        assert raw_value != plaintext, (
            "SECURITY FAILURE: Token is stored in PLAINTEXT in the database!"
        )
        # Fernet tokens start with 'gAAAAA' (base64 encoded)
        assert raw_value.startswith("gAAAAA"), (
            f"Raw value doesn't look like Fernet ciphertext: {raw_value[:20]}..."
        )

    def test_null_token_handled(self, db_session):
        """A user with no access token should have None, not a crash."""
        user = User(
            github_id=44,
            username="no_token",
            name="No Token User",
            access_token=None,
        )
        db_session.add(user)
        db_session.commit()

        fetched = db_session.query(User).filter(User.username == "no_token").first()
        assert fetched.access_token is None

    def test_different_tokens_produce_different_ciphertext(self, db_session):
        """Two different plaintext tokens should produce different ciphertext (Fernet uses random IV)."""
        user1 = User(github_id=45, username="user_a", access_token="token_aaa")
        user2 = User(github_id=46, username="user_b", access_token="token_bbb")
        db_session.add_all([user1, user2])
        db_session.commit()

        result = db_session.execute(text("SELECT username, access_token FROM users WHERE username IN ('user_a', 'user_b')"))
        rows = {r[0]: r[1] for r in result}

        assert rows["user_a"] != rows["user_b"]
