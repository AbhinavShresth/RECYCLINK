"""allow only one reviewed correction per prediction"""

from alembic import op

revision = "15a85e62bc04"
down_revision = "4e381fc43f19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("classification_feedback") as batch:
            batch.create_unique_constraint("uq_classification_feedback_once", ["classification_id"])
    else:
        op.create_unique_constraint("uq_classification_feedback_once", "classification_feedback", ["classification_id"])


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("classification_feedback") as batch:
            batch.drop_constraint("uq_classification_feedback_once", type_="unique")
    else:
        op.drop_constraint("uq_classification_feedback_once", "classification_feedback", type_="unique")
