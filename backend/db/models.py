import os
from cryptography.fernet import Fernet
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator
from .database import Base

ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", Fernet.generate_key().decode())
fernet = Fernet(ENCRYPTION_KEY.encode())

class EncryptedString(TypeDecorator):
    """
    Transparently encrypts/decrypts strings using Fernet symmetric encryption.
    """
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return fernet.encrypt(value.encode()).decode()
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            try:
                return fernet.decrypt(value.encode()).decode()
            except Exception:
                return None
        return None

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(Integer, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    name = Column(String, nullable=True)
    
    access_token = Column(EncryptedString, nullable=False) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    pull_requests = relationship("PullRequest", back_populates="author")
    commits = relationship("Commit", back_populates="author")

class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, index=True)
    github_pr_id = Column(Integer, unique=True, index=True)
    repo_name = Column(String, index=True)
    number = Column(Integer)
    title = Column(String)
    state = Column(String) 
    is_merged = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    merged_at = Column(DateTime(timezone=True), nullable=True)

    author_id = Column(Integer, ForeignKey("users.id"))
    author = relationship("User", back_populates="pull_requests")

class Commit(Base):
    __tablename__ = "commits"

    id = Column(Integer, primary_key=True, index=True)
    sha = Column(String, unique=True, index=True)
    repo_name = Column(String, index=True)
    message = Column(String)
    
    committed_at = Column(DateTime(timezone=True))

    author_id = Column(Integer, ForeignKey("users.id"))
    author = relationship("User", back_populates="commits")