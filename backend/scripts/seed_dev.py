import argparse
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.bins import SmartBin
from app.models.identity import (
    RecyclerAcceptedCategory,
    RecyclerProfile,
    RecyclerServiceArea,
    Role,
    User,
    UserProfile,
    UserRole,
    WasteCategory,
)
from app.models.marketplace import (
    CollectionRequest,
    CollectionStatusHistory,
    Notification,
    RecyclerOffer,
    WasteListing,
)
from app.models.recovery import (
    InventoryLedgerEntry,
    InventoryLot,
    MaterialTransaction,
    ProcessingBatch,
    ProcessingInput,
    RecoveredMaterial,
    TransactionStatusEvent,
)
from app.services.bins import apply_reading

CATEGORIES = {
    "plastic": "Plastic",
    "paper": "Paper and cardboard",
    "metal": "Metal",
    "glass": "Glass",
    "organic": "Organic waste",
    "textile": "Textile",
    "electronics": "Electronic waste",
    "other": "Other or uncertain",
}
DEMO = [
    ("user@recyclink.demo", "Aarav Sharma", ["USER"]),
    ("recycler@recyclink.demo", "GreenCycle Delhi", ["USER", "RECYCLER"]),
    ("both@recyclink.demo", "Nisha Verma", ["USER", "RECYCLER"]),
    ("admin@recyclink.demo", "RecycLink Admin", ["USER", "ADMIN"]),
]


def seed_marketplace_and_recovery(db, now: datetime) -> None:
    users = {email: db.scalar(select(User).where(User.email == email)) for email, _, _ in DEMO}
    household = users["user@recyclink.demo"]
    recycler = users["recycler@recyclink.demo"]
    dual = users["both@recyclink.demo"]

    profile = db.get(RecyclerProfile, recycler.id)
    if profile is None:
        profile = RecyclerProfile(user_id=recycler.id, business_name="GreenCycle Delhi", description="Fictional demonstration recycler", min_pickup_grams=500, max_capacity_grams=80_000_000)
        profile.service_areas = [RecyclerServiceArea(label="Central demo area", center_latitude=28.6139, center_longitude=77.2090, radius_meters=20_000)]
        profile.accepted_categories = [RecyclerAcceptedCategory(category_code=code, indicative_price_minor_per_kg=price) for code, price in [("paper", 2500), ("plastic", 4200), ("metal", 7800)]]
        db.add(profile)

    dual_profile = db.get(RecyclerProfile, dual.id)
    if dual_profile is None:
        dual_profile = RecyclerProfile(user_id=dual.id, business_name="LoopBack Materials", description="Fictional dual-role demonstration account", min_pickup_grams=1000, max_capacity_grams=40_000_000)
        dual_profile.service_areas = [RecyclerServiceArea(label="East demo area", center_latitude=28.6280, center_longitude=77.2770, radius_meters=12_000)]
        dual_profile.accepted_categories = [RecyclerAcceptedCategory(category_code="paper", indicative_price_minor_per_kg=2300)]
        db.add(dual_profile)
    db.flush()

    marker = "[SIMULATED-DEMO:paper-complete]"
    if db.scalar(select(WasteListing.id).where(WasteListing.description == marker)):
        return

    completed_listing = WasteListing(owner_id=household.id, category_code="paper", quantity_grams=8000, condition="Dry, flattened, and bundled", description=marker, pickup_address="Fictional pickup point, Central Delhi", latitude=28.6139, longitude=77.2090, status="CLOSED", created_at=now - timedelta(days=18), updated_at=now - timedelta(days=17))
    scheduled_listing = WasteListing(owner_id=household.id, category_code="plastic", quantity_grams=4500, condition="Rinsed containers", description="[SIMULATED-DEMO:plastic-scheduled]", pickup_address="Fictional pickup point, Central Delhi", latitude=28.6200, longitude=77.2150, preferred_start=now + timedelta(days=1), preferred_end=now + timedelta(days=2), status="ACCEPTED", created_at=now - timedelta(days=3), updated_at=now - timedelta(days=1))
    open_listing = WasteListing(owner_id=dual.id, category_code="paper", quantity_grams=3200, condition="Clean cardboard", description="[SIMULATED-DEMO:paper-open]", pickup_address="Fictional pickup point, East Delhi", latitude=28.6280, longitude=77.2770, status="OPEN", created_at=now - timedelta(days=1), updated_at=now - timedelta(days=1))
    db.add_all([completed_listing, scheduled_listing, open_listing])
    db.flush()

    completed_offer = RecyclerOffer(listing_id=completed_listing.id, recycler_id=recycler.id, price_minor_per_kg=2500, pickup_fee_minor=0, notes="Simulated accepted demo offer", status="ACCEPTED", created_at=now - timedelta(days=18))
    scheduled_offer = RecyclerOffer(listing_id=scheduled_listing.id, recycler_id=recycler.id, price_minor_per_kg=4200, pickup_fee_minor=1500, proposed_pickup_at=now + timedelta(days=1), notes="Simulated scheduled demo offer", status="ACCEPTED", created_at=now - timedelta(days=2))
    db.add_all([completed_offer, scheduled_offer])
    db.flush()

    complete_id = now - timedelta(days=17)
    completed_collection = CollectionRequest(listing_id=completed_listing.id, offer_id=completed_offer.id, user_id=household.id, recycler_id=recycler.id, estimated_quantity_grams=8000, actual_quantity_grams=7800, scheduled_at=now - timedelta(days=17), collected_at=complete_id + timedelta(hours=2), completed_at=complete_id + timedelta(hours=4), status="COMPLETED", created_at=now - timedelta(days=18), updated_at=complete_id + timedelta(hours=4))
    scheduled_collection = CollectionRequest(listing_id=scheduled_listing.id, offer_id=scheduled_offer.id, user_id=household.id, recycler_id=recycler.id, estimated_quantity_grams=4500, scheduled_at=now + timedelta(days=1), status="SCHEDULED", created_at=now - timedelta(days=2), updated_at=now - timedelta(days=1))
    db.add_all([completed_collection, scheduled_collection])
    db.flush()

    states = ["ACCEPTED", "SCHEDULED", "EN_ROUTE", "ARRIVED", "COLLECTED", "WEIGHED", "COMPLETED"]
    for index, state in enumerate(states):
        db.add(CollectionStatusHistory(collection_id=completed_collection.id, actor_id=recycler.id, from_status=states[index - 1] if index else None, to_status=state, reason="Simulated demonstration lifecycle", created_at=complete_id + timedelta(minutes=index * 20)))
    db.add_all([
        CollectionStatusHistory(collection_id=scheduled_collection.id, actor_id=recycler.id, from_status=None, to_status="ACCEPTED", reason="Simulated demonstration offer accepted", created_at=now - timedelta(days=2)),
        CollectionStatusHistory(collection_id=scheduled_collection.id, actor_id=recycler.id, from_status="ACCEPTED", to_status="SCHEDULED", reason="Simulated demonstration pickup scheduled", created_at=now - timedelta(days=1)),
        Notification(user_id=household.id, event_type="COLLECTION_COMPLETED", title="Demo collection completed", body="A fictional paper pickup was weighed and completed.", collection_id=completed_collection.id, created_at=complete_id + timedelta(hours=4)),
        Notification(user_id=recycler.id, event_type="COLLECTION_SCHEDULED", title="Demo pickup scheduled", body="A fictional plastic pickup is scheduled.", collection_id=scheduled_collection.id, created_at=now - timedelta(days=1)),
    ])

    input_lot = InventoryLot(recycler_id=recycler.id, category_code="paper", origin_collection_id=completed_collection.id, initial_quantity_grams=7800, location_label="Demo facility A", acquired_cost_minor=19500, created_at=complete_id + timedelta(hours=5))
    db.add(input_lot)
    db.flush()
    db.add(InventoryLedgerEntry(lot_id=input_lot.id, recycler_id=recycler.id, quantity_delta_grams=7800, movement_type="RECEIVED", reason="SIMULATED demo facility receipt", collection_id=completed_collection.id, actor_id=recycler.id, created_at=complete_id + timedelta(hours=5)))

    batch = ProcessingBatch(recycler_id=recycler.id, process_type="Demo sorting and baling", input_quantity_grams=5000, recovered_quantity_grams=4200, residual_quantity_grams=800, notes="SIMULATED demo process; residual retained in the batch record", created_at=now - timedelta(days=10))
    db.add(batch)
    db.flush()
    db.add(ProcessingInput(batch_id=batch.id, lot_id=input_lot.id, quantity_grams=5000))
    db.add(InventoryLedgerEntry(lot_id=input_lot.id, recycler_id=recycler.id, quantity_delta_grams=-5000, movement_type="PROCESSING_INPUT", reason="SIMULATED demo processing input", processing_batch_id=batch.id, actor_id=recycler.id, created_at=now - timedelta(days=10)))
    output_lot = InventoryLot(recycler_id=recycler.id, category_code="paper", source_batch_id=batch.id, initial_quantity_grams=4200, location_label="Demo recovered paper stock", created_at=now - timedelta(days=10))
    db.add(output_lot)
    db.flush()
    db.add_all([
        RecoveredMaterial(batch_id=batch.id, lot_id=output_lot.id, material_code="paper", quantity_grams=4200, quality_grade="Demo sorted"),
        InventoryLedgerEntry(lot_id=output_lot.id, recycler_id=recycler.id, quantity_delta_grams=4200, movement_type="RECOVERED_OUTPUT", reason="SIMULATED demo recovered material", processing_batch_id=batch.id, actor_id=recycler.id, created_at=now - timedelta(days=10)),
    ])
    sale_quantity = 1500
    sale_price = 45000
    amount_minor = (sale_quantity * sale_price + 500) // 1000
    transaction = MaterialTransaction(recycler_id=recycler.id, lot_id=output_lot.id, material_code="paper", quantity_grams=sale_quantity, unit_price_minor_per_kg=sale_price, amount_minor=amount_minor, currency="INR", buyer_reference="SIMULATED-DEMO-BUYER-01", payment_status="PAID", payment_reference="SIMULATED-DEMO-PAID-01", payment_confirmed_at=now - timedelta(days=8), created_at=now - timedelta(days=9))
    db.add(transaction)
    db.flush()
    db.add_all([
        InventoryLedgerEntry(lot_id=output_lot.id, recycler_id=recycler.id, quantity_delta_grams=-sale_quantity, movement_type="SALE", reason="SIMULATED demo material sale", transaction_id=transaction.id, actor_id=recycler.id, created_at=now - timedelta(days=9)),
        TransactionStatusEvent(transaction_id=transaction.id, actor_id=recycler.id, from_status="UNPAID", to_status="PAID", reference="SIMULATED-DEMO-PAID-01", created_at=now - timedelta(days=8)),
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed explicitly simulated development records")
    parser.add_argument("--demo", action="store_true", help="Create fictional accounts with the local demo password")
    args = parser.parse_args()
    if os.getenv("APP_ENV", "development").lower() == "production":
        raise SystemExit("Refusing to seed demo data when APP_ENV=production")
    with SessionLocal.begin() as db:
        for code, description in [("USER", "Standard platform user"), ("RECYCLER", "Recycler capabilities"), ("ADMIN", "Platform administrator")]:
            if db.get(Role, code) is None:
                db.add(Role(code=code, description=description))
        for code, display in CATEGORIES.items():
            if db.get(WasteCategory, code) is None:
                db.add(WasteCategory(code=code, display_name=display))
        db.flush()
        if args.demo:
            password = os.getenv("DEMO_PASSWORD", "recyclink-demo-2026")
            for email, name, roles in DEMO:
                user = db.scalar(select(User).where(User.email == email))
                if user is None:
                    user = User(email=email, password_hash=hash_password(password))
                    user.profile = UserProfile(full_name=name, preferred_language="en")
                    user.roles = [UserRole(role_code=role) for role in roles]
                    db.add(user)
            db.flush()
            demo_bins = [
                ("DL-CENTRAL-01", "Central market paper bin", "paper", 28.6139, 77.2090, 120000, [48, 61, 74, 93], "Central"),
                ("DL-CENTRAL-02", "Metro plastic bin", "plastic", 28.6328, 77.2197, 80000, [30, 41, 59, 77], "Central"),
                ("DL-WEST-01", "Community organic bin", "organic", 28.6517, 77.1100, 150000, [25, 38, 42, 46], "West"),
                ("DL-EAST-01", "Market metal bin", "metal", 28.6280, 77.2770, 60000, [65, 76, 88, 100], "East"),
            ]
            now = datetime.now(UTC)
            seed_marketplace_and_recovery(db, now)
            for code, label, category, lat, lon, capacity, fills, area in demo_bins:
                row = db.scalar(select(SmartBin).where(SmartBin.bin_code == code))
                if row is None:
                    row = SmartBin(bin_code=code, label=label, category_code=category, latitude=lat, longitude=lon, capacity_grams=capacity, fill_percent=0, battery_percent=95, connectivity_status="ONLINE", operational_status="ACTIVE", sensor_source="SIMULATED", service_area=area)
                    db.add(row)
                    db.flush()
                    for days_ago, fill in zip([21, 14, 7, 0], fills, strict=False):
                        apply_reading(db, row, fill, min(100, 90+days_ago*0.3), "ONLINE", reported_at=now-timedelta(days=days_ago))
    print("Base roles and categories are ready. Demo identities were created only when --demo was provided.")


if __name__ == "__main__":
    main()
