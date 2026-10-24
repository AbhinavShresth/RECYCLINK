from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class WasteClassification(Base):
    __tablename__ = "waste_classifications"
    __table_args__ = (Index("ix_classification_user_created", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    predicted_class: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_class: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    top_predictions_json: Mapped[str] = mapped_column(Text, nullable=False)
    needs_confirmation: Mapped[bool] = mapped_column(nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ClassificationFeedback(Base):
    __tablename__ = "classification_feedback"
    __table_args__ = (UniqueConstraint("classification_id", name="uq_classification_feedback_once"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    classification_id: Mapped[UUID] = mapped_column(ForeignKey("waste_classifications.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    confirmed_class: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
