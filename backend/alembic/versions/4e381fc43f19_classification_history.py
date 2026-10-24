"""classification history and reviewed feedback"""
import sqlalchemy as sa

from alembic import op

revision = "4e381fc43f19"
down_revision = "ce77d0b9dc9a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "waste_classifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("image_sha256", sa.String(length=64), nullable=False),
        sa.Column("predicted_class", sa.String(length=32), nullable=False),
        sa.Column("candidate_class", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("top_predictions_json", sa.Text(), nullable=False),
        sa.Column("needs_confirmation", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_classification_user_created", "waste_classifications", ["user_id", "created_at"])
    op.create_table(
        "classification_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("classification_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("confirmed_class", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["classification_id"], ["waste_classifications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_classification_feedback_classification_id"), "classification_feedback", ["classification_id"])
    op.create_index(op.f("ix_classification_feedback_user_id"), "classification_feedback", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_classification_feedback_user_id"), table_name="classification_feedback")
    op.drop_index(op.f("ix_classification_feedback_classification_id"), table_name="classification_feedback")
    op.drop_table("classification_feedback")
    op.drop_index("ix_classification_user_created", table_name="waste_classifications")
    op.drop_table("waste_classifications")
