"""identity integrity constraints"""

from alembic import op

revision = 'ce77d0b9dc9a'
down_revision = '4634750eecf7'
branch_labels = None
depends_on = None

def upgrade() -> None:
    constraints = [
        ("recycler_profiles", "ck_recycler_min_pickup_nonnegative", "min_pickup_grams >= 0"),
        ("recycler_profiles", "ck_recycler_capacity_positive", "max_capacity_grams IS NULL OR max_capacity_grams > 0"),
        ("recycler_service_areas", "ck_service_area_latitude", "center_latitude >= -90 AND center_latitude <= 90"),
        ("recycler_service_areas", "ck_service_area_longitude", "center_longitude >= -180 AND center_longitude <= 180"),
        ("recycler_service_areas", "ck_service_area_radius", "radius_meters >= 100 AND radius_meters <= 500000"),
        ("recycler_accepted_categories", "ck_price_nonnegative", "indicative_price_minor_per_kg IS NULL OR indicative_price_minor_per_kg >= 0"),
    ]
    sqlite = op.get_bind().dialect.name == "sqlite"
    for table, name, expression in constraints:
        if sqlite:
            with op.batch_alter_table(table) as batch:
                batch.create_check_constraint(name, expression)
        else:
            op.create_check_constraint(name, table, expression)

def downgrade() -> None:
    constraints = [
        ("recycler_accepted_categories", "ck_price_nonnegative"),
        ("recycler_service_areas", "ck_service_area_radius"),
        ("recycler_service_areas", "ck_service_area_longitude"),
        ("recycler_service_areas", "ck_service_area_latitude"),
        ("recycler_profiles", "ck_recycler_capacity_positive"),
        ("recycler_profiles", "ck_recycler_min_pickup_nonnegative"),
    ]
    sqlite = op.get_bind().dialect.name == "sqlite"
    for table, name in constraints:
        if sqlite:
            with op.batch_alter_table(table) as batch:
                batch.drop_constraint(name, type_="check")
        else:
            op.drop_constraint(name, table, type_="check")
