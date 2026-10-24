import hashlib
import random
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_csrf, require_roles
from app.db.session import get_db
from app.models.bins import BinAlert, BinCollectionEvent, BinSensorReading, SmartBin
from app.models.identity import User, WasteCategory
from app.schemas.bins import BinCollectionIn, BinCreate, BinReadingIn, SimulatorTickIn
from app.services.bins import apply_reading, update_alerts

router = APIRouter(prefix="/bins", tags=["smart bins"])


def bin_view(row: SmartBin) -> dict:
    return {"id": str(row.id), "bin_code": row.bin_code, "label": row.label, "category_code": row.category_code, "latitude": row.latitude, "longitude": row.longitude, "capacity_grams": row.capacity_grams, "fill_percent": row.fill_percent, "estimated_fill_grams": round(row.capacity_grams * row.fill_percent / 100), "battery_percent": row.battery_percent, "connectivity_status": row.connectivity_status, "operational_status": row.operational_status, "sensor_source": row.sensor_source, "service_area": row.service_area, "last_reported_at": row.last_reported_at.isoformat() if row.last_reported_at else None}


@router.get("")
def get_bins(category: str | None = None, service_area: str | None = None, connectivity: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    query = select(SmartBin)
    if category:
        query = query.where(SmartBin.category_code == category)
    if service_area:
        query = query.where(SmartBin.service_area == service_area)
    if connectivity:
        query = query.where(SmartBin.connectivity_status == connectivity.upper())
    return [bin_view(row) for row in db.scalars(query.order_by(SmartBin.label)).all()]


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def create_bin(payload: BinCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN"))) -> dict:
    category = db.get(WasteCategory, payload.category_code)
    if category is None or not category.is_active:
        raise HTTPException(422, "Choose an available material category")
    row = SmartBin(bin_code=payload.bin_code.upper(), label=payload.label, category_code=payload.category_code, latitude=payload.latitude, longitude=payload.longitude, capacity_grams=payload.capacity_grams, fill_percent=payload.fill_percent, battery_percent=payload.battery_percent, connectivity_status="ONLINE", operational_status="ACTIVE", sensor_source="SIMULATED", service_area=payload.service_area)
    db.add(row)
    db.flush()
    apply_reading(db, row, payload.fill_percent, payload.battery_percent, "ONLINE", reported_by=user.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A bin with this code already exists") from None
    db.refresh(row)
    return bin_view(row)


@router.get("/{bin_id}/readings")
def get_readings(bin_id: UUID, limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    if db.get(SmartBin, bin_id) is None:
        raise HTTPException(404, "Bin not found")
    readings = db.scalars(select(BinSensorReading).where(BinSensorReading.bin_id == bin_id).order_by(BinSensorReading.reported_at.desc()).limit(limit)).all()
    return [{"id": str(r.id), "fill_percent": r.fill_percent, "battery_percent": r.battery_percent, "connectivity_status": r.connectivity_status, "sensor_source": r.sensor_source, "reported_at": r.reported_at.isoformat()} for r in readings]


@router.post("/{bin_id}/readings", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def record_admin_reading(bin_id: UUID, payload: BinReadingIn, db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN"))) -> dict:
    row = db.scalar(select(SmartBin).where(SmartBin.id == bin_id).with_for_update())
    if row is None:
        raise HTTPException(404, "Bin not found")
    apply_reading(db, row, payload.fill_percent, payload.battery_percent, payload.connectivity_status, reported_by=user.id)
    db.commit()
    db.refresh(row)
    return bin_view(row)


@router.get("/alerts")
def get_alerts(open_only: bool = True, severity: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    query = select(BinAlert)
    if open_only:
        query = query.where(BinAlert.is_open.is_(True))
    if severity:
        query = query.where(BinAlert.severity == severity.upper())
    alerts = db.scalars(query.order_by(BinAlert.created_at.desc()).limit(300)).all()
    result = []
    for alert in alerts:
        row = db.get(SmartBin, alert.bin_id)
        result.append({"id": str(alert.id), "bin_id": str(row.id), "bin_code": row.bin_code, "label": row.label, "service_area": row.service_area, "alert_type": alert.alert_type, "severity": alert.severity, "message": alert.message, "is_open": alert.is_open, "created_at": alert.created_at.isoformat(), "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None})
    return result


@router.post("/alerts/evaluate", dependencies=[Depends(require_csrf)])
def evaluate_alerts(db: Session = Depends(get_db), _: User = Depends(require_roles("ADMIN"))) -> dict:
    now = datetime.now(UTC)
    rows = db.scalars(select(SmartBin).order_by(SmartBin.id).with_for_update()).all()
    for row in rows:
        update_alerts(db, row, now=now)
    db.commit()
    return {"evaluated_bins": len(rows), "evaluated_at": now.isoformat()}


@router.post("/simulator/tick", dependencies=[Depends(require_csrf)])
def simulator_tick(payload: SimulatorTickIn, db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN"))) -> dict:
    if payload.fill_increment_max < payload.fill_increment_min:
        raise HTTPException(422, "Maximum fill increment must be at least the minimum")
    rows = db.scalars(select(SmartBin).where(SmartBin.sensor_source == "SIMULATED").order_by(SmartBin.bin_code).with_for_update()).all()
    now = datetime.now(UTC)
    for row in rows:
        stable_seed = int.from_bytes(hashlib.sha256(f"{payload.seed}:{row.bin_code}".encode()).digest()[:8], "big") if payload.seed is not None else None
        rng = random.Random(stable_seed)
        noise = rng.gauss(0, 0.6)
        increase = rng.uniform(payload.fill_increment_min, payload.fill_increment_max) + noise
        fill = min(100.0, max(0.0, row.fill_percent + increase))
        offline = rng.random() < payload.offline_probability
        battery = max(0.0, (row.battery_percent if row.battery_percent is not None else 100) - rng.uniform(0.1, 0.8))
        apply_reading(db, row, fill, battery, "OFFLINE" if offline else "ONLINE", reported_at=now, reported_by=user.id)
    # Device-backed bins are not mutated by the simulator, but stale/offline alert conditions are evaluated.
    for row in db.scalars(select(SmartBin).where(SmartBin.sensor_source == "DEVICE").order_by(SmartBin.id).with_for_update()).all():
        update_alerts(db, row, now=now, reported_by=user.id)
    db.commit()
    return {"simulated_readings": len(rows), "simulated_at": now.isoformat(), "seed": payload.seed, "sensor_data_label": "SIMULATED", "fill_increment_range_percent": [payload.fill_increment_min, payload.fill_increment_max], "offline_probability": payload.offline_probability}


@router.post("/{bin_id}/report-overflow", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def report_overflow(bin_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    row = db.scalar(select(SmartBin).where(SmartBin.id == bin_id).with_for_update())
    if row is None:
        raise HTTPException(404, "Bin not found")
    open_alert = db.scalar(select(BinAlert.id).where(BinAlert.bin_id == row.id, BinAlert.alert_type == "USER_REPORTED_OVERFLOW", BinAlert.is_open.is_(True)))
    if open_alert:
        return JSONResponse(status_code=200, content={"reported": True, "duplicate_open_alert": True, "alert_id": str(open_alert)})
    alert = BinAlert(bin_id=row.id, alert_type="USER_REPORTED_OVERFLOW", severity="HIGH", message="A platform user reported this bin as full or overflowing.", is_open=True, reported_by=user.id)
    db.add(alert)
    db.commit()
    return {"reported": True, "duplicate_open_alert": False, "alert_id": str(alert.id), "sensor_state_changed": False}


@router.post("/{bin_id}/collect", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def collect_bin(bin_id: UUID, payload: BinCollectionIn, db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER", "ADMIN"))) -> dict:
    row = db.scalar(select(SmartBin).where(SmartBin.id == bin_id).with_for_update())
    if row is None:
        raise HTTPException(404, "Bin not found")
    estimated = round(row.capacity_grams * row.fill_percent / 100)
    if payload.collected_quantity_grams > estimated:
        raise HTTPException(409, f"Recorded amount exceeds the current fill estimate ({estimated} grams)")
    new_fill = max(0.0, row.fill_percent - payload.collected_quantity_grams / row.capacity_grams * 100)
    event = BinCollectionEvent(bin_id=row.id, collected_quantity_grams=payload.collected_quantity_grams, actor_id=user.id, notes=payload.notes)
    db.add(event)
    apply_reading(db, row, new_fill, row.battery_percent, "ONLINE", reported_by=user.id)
    db.commit()
    return {"event_id": str(event.id), "bin": bin_view(row), "collected_quantity_grams": payload.collected_quantity_grams}


@router.get("/{bin_id}/collections")
def bin_collections(bin_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    if db.get(SmartBin, bin_id) is None:
        raise HTTPException(404, "Bin not found")
    events = db.scalars(select(BinCollectionEvent).where(BinCollectionEvent.bin_id == bin_id).order_by(BinCollectionEvent.created_at.desc()).limit(100)).all()
    return [{"id": str(event.id), "collected_quantity_grams": event.collected_quantity_grams, "notes": event.notes, "created_at": event.created_at.isoformat()} for event in events]
