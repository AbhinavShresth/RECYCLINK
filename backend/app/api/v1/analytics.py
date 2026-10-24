from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.session import get_db
from app.models.identity import User
from app.services.analytics import admin_analytics, recycler_analytics, user_analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _period(start: datetime | None, end: datetime | None) -> tuple[datetime | None, datetime | None]:
    if start and start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end and end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    if start and end and start >= end:
        raise HTTPException(422, "start must be earlier than the exclusive end")
    return start, end


@router.get("/user")
def get_user_analytics(start: datetime | None = Query(default=None), end: datetime | None = Query(default=None), db: Session = Depends(get_db), user: User = Depends(require_roles("USER"))) -> dict:
    start, end = _period(start, end)
    return user_analytics(db, user.id, start, end)


@router.get("/recycler")
def get_recycler_analytics(start: datetime | None = Query(default=None), end: datetime | None = Query(default=None), db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER"))) -> dict:
    start, end = _period(start, end)
    return recycler_analytics(db, user.id, start, end)


@router.get("/admin")
def get_admin_analytics(start: datetime | None = Query(default=None), end: datetime | None = Query(default=None), db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN"))) -> dict:
    start, end = _period(start, end)
    return admin_analytics(db, start, end)
