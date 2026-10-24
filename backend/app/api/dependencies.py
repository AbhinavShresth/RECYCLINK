from collections.abc import Callable
from hmac import compare_digest
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.session import get_db
from app.models.identity import User, UserRole

settings = get_settings()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("recyclink_session")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid or expired") from None
    user = db.scalar(select(User).options(selectinload(User.roles).selectinload(UserRole.role), selectinload(User.profile)).where(User.id == user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account unavailable")
    return user


def require_roles(*allowed: str) -> Callable:
    def dependency(user: User = Depends(get_current_user)) -> User:
        roles = {entry.role_code for entry in user.roles}
        if not roles.intersection(allowed):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This action is not available for your role")
        return user

    return dependency


def require_csrf(request: Request) -> None:
    header = request.headers.get("x-csrf-token", "")
    cookie = request.cookies.get("csrf_token", "")
    if not header or not cookie or not compare_digest(header, cookie):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
