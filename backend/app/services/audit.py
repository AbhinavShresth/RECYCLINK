import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def record_audit(db: Session, actor_id: UUID, action: str, entity_type: str, entity_id: UUID | str, details: dict) -> None:
    """Persist bounded operational metadata only; callers must omit addresses, secrets and transcripts."""
    safe_details = json.dumps(details, separators=(",", ":"), ensure_ascii=True)
    if len(safe_details) > 2000:
        raise ValueError("Audit metadata exceeds the safe size limit")
    db.add(AuditLog(actor_id=actor_id, action_code=action, entity_type=entity_type, entity_id=str(entity_id), details_json=safe_details))
