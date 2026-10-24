"""persist road-routed plans and stop order"""
import sqlalchemy as sa

from alembic import op

revision = "b6ad90c3571e"
down_revision = "8df2c093a6e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "route_plans",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("recycler_id", sa.Uuid(), nullable=False),
        sa.Column("start_latitude", sa.Float(), nullable=False), sa.Column("start_longitude", sa.Float(), nullable=False),
        sa.Column("end_latitude", sa.Float(), nullable=False), sa.Column("end_longitude", sa.Float(), nullable=False),
        sa.Column("baseline_distance_meters", sa.Float(), nullable=False), sa.Column("optimized_distance_meters", sa.Float(), nullable=False),
        sa.Column("baseline_duration_seconds", sa.Float(), nullable=False), sa.Column("optimized_duration_seconds", sa.Float(), nullable=False),
        sa.Column("distance_saved_percentage", sa.Float()), sa.Column("duration_saved_percentage", sa.Float()),
        sa.Column("geometry_json", sa.Text(), nullable=False), sa.Column("router_data_version", sa.String(80)),
        sa.Column("method", sa.String(200), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recycler_id"], ["recycler_profiles.user_id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_route_plans_recycler_created", "route_plans", ["recycler_id", "created_at"])
    op.create_table(
        "route_stops",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("route_id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False), sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["route_id"], ["route_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_id"], ["collection_requests.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("route_id", "sequence", name="uq_route_stop_sequence"),
        sa.UniqueConstraint("route_id", "collection_id", name="uq_route_stop_collection"),
    )
    op.create_index(op.f("ix_route_stops_route_id"), "route_stops", ["route_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_route_stops_route_id"), table_name="route_stops")
    op.drop_table("route_stops")
    op.drop_index("ix_route_plans_recycler_created", table_name="route_plans")
    op.drop_table("route_plans")
