from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.bins import BinAlert, BinSensorReading, SmartBin


def apply_reading(db: Session, bin_row: SmartBin, fill_percent: float, battery_percent: float | None, connectivity_status: str, *, reported_at: datetime | None = None, reported_by=None) -> None:
    now = reported_at or datetime.now(UTC)
    bin_row.fill_percent = min(100.0, max(0.0, fill_percent))
    bin_row.battery_percent = battery_percent
    bin_row.connectivity_status = connectivity_status
    bin_row.last_reported_at = now
    db.add(BinSensorReading(bin_id=bin_row.id, fill_percent=bin_row.fill_percent, battery_percent=battery_percent, connectivity_status=connectivity_status, sensor_source=bin_row.sensor_source, reported_at=now))
    update_alerts(db, bin_row, now=now, reported_by=reported_by)


def update_alerts(db: Session, bin_row: SmartBin, *, now: datetime | None = None, reported_by=None) -> None:
    settings = get_settings()
    now = now or datetime.now(UTC)
    active: dict[str, tuple[str, str]] = {}
    if bin_row.fill_percent >= settings.bin_critical_fill_percent:
        active["OVERFLOW"] = ("CRITICAL", "Bin is at or above its critical fill threshold.")
    elif bin_row.fill_percent >= settings.bin_high_fill_percent:
        active["HIGH_FILL"] = ("HIGH", "Bin has reached the high fill threshold.")
    elif bin_row.fill_percent >= settings.bin_warning_fill_percent:
        active["FILL_WARNING"] = ("WARNING", "Bin has reached the warning fill threshold.")
    if bin_row.connectivity_status == "OFFLINE":
        active["OFFLINE"] = ("HIGH", "Bin sensor reports offline connectivity.")
    if bin_row.battery_percent is not None and bin_row.battery_percent <= 20:
        active["LOW_BATTERY"] = ("WARNING", "Bin sensor battery is at or below 20 percent.")
    last_seen = bin_row.last_reported_at
    if last_seen and last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=UTC)
    if last_seen and now - last_seen > timedelta(hours=settings.bin_stale_after_hours):
        active["STALE"] = ("WARNING", "Bin has not reported within the configured stale-data interval.")
    existing = db.scalars(select(BinAlert).where(BinAlert.bin_id == bin_row.id, BinAlert.is_open.is_(True)).with_for_update()).all()
    by_type = {row.alert_type: row for row in existing}
    for alert_type, alert in by_type.items():
        if alert_type not in active:
            alert.is_open = False
            alert.resolved_at = now
    for alert_type, (severity, message) in active.items():
        if alert_type not in by_type:
            db.add(BinAlert(bin_id=bin_row.id, alert_type=alert_type, severity=severity, message=message, is_open=True, reported_by=reported_by))
