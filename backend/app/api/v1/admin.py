import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.identity import User

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/audit-logs")
def get_audit_logs(action: str | None = Query(default=None, max_length=48), limit: int = Query(default=100, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db), _: User = Depends(require_roles("ADMIN"))) -> list[dict]:
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action_code == action.upper())
    rows = db.scalars(query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)).all()
    return [{"id": str(row.id), "actor_id": str(row.actor_id), "action": row.action_code, "entity_type": row.entity_type, "entity_id": row.entity_id, "details": json.loads(row.details_json), "created_at": row.created_at.isoformat()} for row in rows]
