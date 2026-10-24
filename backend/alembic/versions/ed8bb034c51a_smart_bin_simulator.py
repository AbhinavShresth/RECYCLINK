"""smart bin sensors, alerts, and collection events"""
import sqlalchemy as sa

from alembic import op

revision = "ed8bb034c51a"
down_revision = "c4d7ee9b183b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "smart_bins",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("bin_code", sa.String(40), nullable=False),
        sa.Column("label", sa.String(160), nullable=False), sa.Column("category_code", sa.String(32), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False), sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("capacity_grams", sa.Integer(), nullable=False), sa.Column("fill_percent", sa.Float(), nullable=False),
        sa.Column("battery_percent", sa.Float()), sa.Column("connectivity_status", sa.String(10), nullable=False),
        sa.Column("operational_status", sa.String(20), nullable=False), sa.Column("sensor_source", sa.String(12), nullable=False),
        sa.Column("service_area", sa.String(120)), sa.Column("last_reported_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_bin_latitude"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_bin_longitude"),
        sa.CheckConstraint("capacity_grams > 0", name="ck_bin_capacity_positive"),
        sa.CheckConstraint("fill_percent >= 0 AND fill_percent <= 100", name="ck_bin_fill_range"),
        sa.CheckConstraint("battery_percent IS NULL OR (battery_percent >= 0 AND battery_percent <= 100)", name="ck_bin_battery_range"),
        sa.CheckConstraint("connectivity_status IN ('ONLINE','OFFLINE')", name="ck_bin_connectivity"),
        sa.CheckConstraint("sensor_source IN ('SIMULATED','DEVICE')", name="ck_bin_sensor_source"),
        sa.ForeignKeyConstraint(["category_code"], ["waste_categories.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("bin_code", name="uq_smart_bin_code"),
    )
    op.create_index("ix_bins_category_status", "smart_bins", ["category_code", "operational_status"])
    op.create_table(
        "bin_sensor_readings",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("bin_id", sa.Uuid(), nullable=False),
        sa.Column("fill_percent", sa.Float(), nullable=False), sa.Column("battery_percent", sa.Float()),
        sa.Column("connectivity_status", sa.String(10), nullable=False), sa.Column("sensor_source", sa.String(12), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("fill_percent >= 0 AND fill_percent <= 100", name="ck_bin_reading_fill_range"),
        sa.CheckConstraint("battery_percent IS NULL OR (battery_percent >= 0 AND battery_percent <= 100)", name="ck_bin_reading_battery_range"),
        sa.ForeignKeyConstraint(["bin_id"], ["smart_bins.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bin_readings_bin_time", "bin_sensor_readings", ["bin_id", "reported_at"])
    op.create_table(
        "bin_alerts",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("bin_id", sa.Uuid(), nullable=False),
        sa.Column("alert_type", sa.String(32), nullable=False), sa.Column("severity", sa.String(12), nullable=False),
        sa.Column("message", sa.String(300), nullable=False), sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.Column("reported_by", sa.Uuid()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["bin_id"], ["smart_bins.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reported_by"], ["users.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bin_alerts_open_created", "bin_alerts", ["is_open", "created_at"])
    op.create_index("ix_bin_alerts_bin_open", "bin_alerts", ["bin_id", "is_open"])
    op.create_table(
        "bin_collection_events",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("bin_id", sa.Uuid(), nullable=False),
        sa.Column("collected_quantity_grams", sa.Integer(), nullable=False), sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("notes", sa.String(500)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bin_id"], ["smart_bins.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bin_collection_events_bin_id"), "bin_collection_events", ["bin_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_bin_collection_events_bin_id"), table_name="bin_collection_events")
    op.drop_table("bin_collection_events")
    op.drop_index("ix_bin_alerts_bin_open", table_name="bin_alerts")
    op.drop_index("ix_bin_alerts_open_created", table_name="bin_alerts")
    op.drop_table("bin_alerts")
    op.drop_index("ix_bin_readings_bin_time", table_name="bin_sensor_readings")
    op.drop_table("bin_sensor_readings")
    op.drop_index("ix_bins_category_status", table_name="smart_bins")
    op.drop_table("smart_bins")
