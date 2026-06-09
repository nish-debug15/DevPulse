from typing import Optional

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User
from auth.jwt_handler import verify_session_token


def get_authenticated_user(
    devpulse_session: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
) -> User:
    if not devpulse_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = verify_session_token(devpulse_session)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
