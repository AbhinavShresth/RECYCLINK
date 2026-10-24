"""auditable inventory, processing, recovered lots, and material sales"""
import sqlalchemy as sa

from alembic import op

revision = "c4d7ee9b183b"
down_revision = "b6ad90c3571e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processing_batches",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("recycler_id", sa.Uuid(), nullable=False),
        sa.Column("process_type", sa.String(120), nullable=False), sa.Column("input_quantity_grams", sa.Integer(), nullable=False),
        sa.Column("recovered_quantity_grams", sa.Integer(), nullable=False), sa.Column("residual_quantity_grams", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(1000)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recycler_id"], ["recycler_profiles.user_id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_processing_recycler_created", "processing_batches", ["recycler_id", "created_at"])
    op.create_table(
        "inventory_lots",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("recycler_id", sa.Uuid(), nullable=False),
        sa.Column("category_code", sa.String(32), nullable=False), sa.Column("origin_collection_id", sa.Uuid()),
        sa.Column("source_batch_id", sa.Uuid()), sa.Column("initial_quantity_grams", sa.Integer(), nullable=False),
        sa.Column("location_label", sa.String(120)), sa.Column("acquired_cost_minor", sa.Integer()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("initial_quantity_grams > 0", name="ck_inventory_lot_quantity_positive"),
        sa.ForeignKeyConstraint(["recycler_id"], ["recycler_profiles.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_code"], ["waste_categories.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["origin_collection_id"], ["collection_requests.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_batch_id"], ["processing_batches.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("origin_collection_id", name="uq_inventory_origin_collection"),
    )
    op.create_index("ix_inventory_lots_recycler_category", "inventory_lots", ["recycler_id", "category_code"])
    op.create_table(
        "processing_inputs",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("lot_id", sa.Uuid(), nullable=False), sa.Column("quantity_grams", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["processing_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lot_id"], ["inventory_lots.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_processing_inputs_batch_id"), "processing_inputs", ["batch_id"])
    op.create_table(
        "recovered_materials",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("lot_id", sa.Uuid(), nullable=False), sa.Column("material_code", sa.String(32), nullable=False),
        sa.Column("quantity_grams", sa.Integer(), nullable=False), sa.Column("quality_grade", sa.String(80)),
        sa.CheckConstraint("quantity_grams > 0", name="ck_recovered_quantity_positive"),
        sa.ForeignKeyConstraint(["batch_id"], ["processing_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lot_id"], ["inventory_lots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["material_code"], ["waste_categories.code"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recovered_materials_batch_id"), "recovered_materials", ["batch_id"])
    op.create_table(
        "material_transactions",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("recycler_id", sa.Uuid(), nullable=False),
        sa.Column("lot_id", sa.Uuid(), nullable=False), sa.Column("material_code", sa.String(32), nullable=False),
        sa.Column("quantity_grams", sa.Integer(), nullable=False), sa.Column("unit_price_minor_per_kg", sa.Integer(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False), sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("buyer_reference", sa.String(160)), sa.Column("payment_status", sa.String(10), nullable=False),
        sa.Column("payment_reference", sa.String(160)), sa.Column("payment_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity_grams > 0", name="ck_transaction_quantity_positive"),
        sa.CheckConstraint("unit_price_minor_per_kg >= 0 AND amount_minor >= 0", name="ck_transaction_money_nonnegative"),
        sa.CheckConstraint("payment_status IN ('UNPAID','PAID')", name="ck_transaction_payment_status"),
        sa.ForeignKeyConstraint(["recycler_id"], ["recycler_profiles.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lot_id"], ["inventory_lots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["material_code"], ["waste_categories.code"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_recycler_created", "material_transactions", ["recycler_id", "created_at"])
    op.create_table(
        "inventory_ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("lot_id", sa.Uuid(), nullable=False),
        sa.Column("recycler_id", sa.Uuid(), nullable=False), sa.Column("quantity_delta_grams", sa.Integer(), nullable=False),
        sa.Column("movement_type", sa.String(20), nullable=False), sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("collection_id", sa.Uuid()), sa.Column("processing_batch_id", sa.Uuid()),
        sa.Column("transaction_id", sa.Uuid()), sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity_delta_grams <> 0", name="ck_inventory_movement_nonzero"),
        sa.ForeignKeyConstraint(["lot_id"], ["inventory_lots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recycler_id"], ["recycler_profiles.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_id"], ["collection_requests.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["processing_batch_id"], ["processing_batches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["transaction_id"], ["material_transactions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_ledger_lot_created", "inventory_ledger_entries", ["lot_id", "created_at"])
    op.create_index("ix_inventory_ledger_recycler_created", "inventory_ledger_entries", ["recycler_id", "created_at"])
    op.create_table(
        "transaction_status_events",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False), sa.Column("from_status", sa.String(10), nullable=False),
        sa.Column("to_status", sa.String(10), nullable=False), sa.Column("reference", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["material_transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transaction_status_events_transaction_id"), "transaction_status_events", ["transaction_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_transaction_status_events_transaction_id"), table_name="transaction_status_events")
    op.drop_table("transaction_status_events")
    op.drop_index("ix_inventory_ledger_recycler_created", table_name="inventory_ledger_entries")
    op.drop_index("ix_inventory_ledger_lot_created", table_name="inventory_ledger_entries")
    op.drop_table("inventory_ledger_entries")
    op.drop_index("ix_transactions_recycler_created", table_name="material_transactions")
    op.drop_table("material_transactions")
    op.drop_index(op.f("ix_recovered_materials_batch_id"), table_name="recovered_materials")
    op.drop_table("recovered_materials")
    op.drop_index(op.f("ix_processing_inputs_batch_id"), table_name="processing_inputs")
    op.drop_table("processing_inputs")
    op.drop_index("ix_inventory_lots_recycler_category", table_name="inventory_lots")
    op.drop_table("inventory_lots")
    op.drop_index("ix_processing_recycler_created", table_name="processing_batches")
    op.drop_table("processing_batches")
