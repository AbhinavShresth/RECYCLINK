"""marketplace listings, offers, collection state, and notifications"""
import sqlalchemy as sa

from alembic import op

revision = "8df2c093a6e3"
down_revision = "15a85e62bc04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "waste_listings",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("classification_id", sa.Uuid(), nullable=True), sa.Column("category_code", sa.String(32), nullable=False),
        sa.Column("quantity_grams", sa.Integer(), nullable=False), sa.Column("condition", sa.String(300)),
        sa.Column("description", sa.String(1200)), sa.Column("pickup_address", sa.String(500), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False), sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("preferred_start", sa.DateTime(timezone=True)), sa.Column("preferred_end", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity_grams > 0", name="ck_listing_quantity_positive"),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_listing_latitude"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_listing_longitude"),
        sa.CheckConstraint("status IN ('OPEN','ACCEPTED','CANCELLED','CLOSED')", name="ck_listing_status"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["classification_id"], ["waste_classifications.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_code"], ["waste_categories.code"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_waste_listings_owner_id"), "waste_listings", ["owner_id"])
    op.create_index("ix_listing_status_created", "waste_listings", ["status", "created_at"])
    op.create_index("ix_listing_category_status", "waste_listings", ["category_code", "status"])
    op.create_table(
        "recycler_offers",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("recycler_id", sa.Uuid(), nullable=False), sa.Column("price_minor_per_kg", sa.Integer(), nullable=False),
        sa.Column("pickup_fee_minor", sa.Integer(), nullable=False), sa.Column("proposed_pickup_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)), sa.Column("notes", sa.String(600)),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price_minor_per_kg >= 0", name="ck_offer_price_nonnegative"),
        sa.CheckConstraint("pickup_fee_minor >= 0", name="ck_offer_fee_nonnegative"),
        sa.CheckConstraint("status IN ('SUBMITTED','ACCEPTED','REJECTED','WITHDRAWN','EXPIRED')", name="ck_offer_status"),
        sa.ForeignKeyConstraint(["listing_id"], ["waste_listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recycler_id"], ["recycler_profiles.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("listing_id", "recycler_id", name="uq_offer_listing_recycler"),
    )
    op.create_index(op.f("ix_recycler_offers_recycler_id"), "recycler_offers", ["recycler_id"])
    op.create_index("ix_offer_listing_status", "recycler_offers", ["listing_id", "status"])
    op.create_table(
        "collection_requests",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("offer_id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("recycler_id", sa.Uuid(), nullable=False), sa.Column("estimated_quantity_grams", sa.Integer(), nullable=False),
        sa.Column("actual_quantity_grams", sa.Integer()), sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("collected_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("cancellation_reason", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("estimated_quantity_grams > 0", name="ck_collection_estimated_positive"),
        sa.CheckConstraint("actual_quantity_grams IS NULL OR actual_quantity_grams >= 0", name="ck_collection_actual_nonnegative"),
        sa.CheckConstraint("status IN ('ACCEPTED','SCHEDULED','ASSIGNED','EN_ROUTE','ARRIVED','COLLECTED','WEIGHED','PROCESSING','COMPLETED','CANCELLED','DISPUTED')", name="ck_collection_status"),
        sa.ForeignKeyConstraint(["listing_id"], ["waste_listings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["offer_id"], ["recycler_offers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recycler_id"], ["recycler_profiles.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("listing_id", name="uq_collection_listing"), sa.UniqueConstraint("offer_id", name="uq_collection_offer"),
    )
    op.create_index("ix_collection_user_status", "collection_requests", ["user_id", "status"])
    op.create_index("ix_collection_recycler_status", "collection_requests", ["recycler_id", "status"])
    op.create_table(
        "collection_status_history",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False), sa.Column("from_status", sa.String(20)), sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(500)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["collection_id"], ["collection_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_collection_status_history_collection_id"), "collection_status_history", ["collection_id"])
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False), sa.Column("title", sa.String(160), nullable=False),
        sa.Column("body", sa.String(500), nullable=False), sa.Column("collection_id", sa.Uuid()),
        sa.Column("is_read", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_id"], ["collection_requests.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_user_created", "notifications", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_user_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_collection_status_history_collection_id"), table_name="collection_status_history")
    op.drop_table("collection_status_history")
    op.drop_index("ix_collection_recycler_status", table_name="collection_requests")
    op.drop_index("ix_collection_user_status", table_name="collection_requests")
    op.drop_table("collection_requests")
    op.drop_index("ix_offer_listing_status", table_name="recycler_offers")
    op.drop_index(op.f("ix_recycler_offers_recycler_id"), table_name="recycler_offers")
    op.drop_table("recycler_offers")
    op.drop_index("ix_listing_category_status", table_name="waste_listings")
    op.drop_index("ix_listing_status_created", table_name="waste_listings")
    op.drop_index(op.f("ix_waste_listings_owner_id"), table_name="waste_listings")
    op.drop_table("waste_listings")
