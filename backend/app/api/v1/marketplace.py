from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_csrf, require_roles
from app.db.session import get_db
from app.models.classification import WasteClassification
from app.models.identity import (
    RecyclerAcceptedCategory,
    RecyclerProfile,
    RecyclerServiceArea,
    User,
    WasteCategory,
)
from app.models.marketplace import (
    CollectionRequest,
    CollectionStatusHistory,
    Notification,
    RecyclerOffer,
    WasteListing,
)
from app.schemas.marketplace import ListingCreate, OfferCreate, TransitionIn
from app.services.audit import record_audit
from app.services.geo import meters_between

router = APIRouter(tags=["marketplace and collections"])
ACTIVE = {"ACCEPTED", "SCHEDULED", "ASSIGNED", "EN_ROUTE", "ARRIVED", "COLLECTED", "WEIGHED", "PROCESSING"}
TRANSITIONS = {
    "ACCEPTED": {"SCHEDULED", "ASSIGNED", "CANCELLED", "DISPUTED"},
    "SCHEDULED": {"EN_ROUTE", "CANCELLED", "DISPUTED"},
    "ASSIGNED": {"EN_ROUTE", "CANCELLED", "DISPUTED"},
    "EN_ROUTE": {"ARRIVED", "CANCELLED", "DISPUTED"},
    "ARRIVED": {"COLLECTED", "CANCELLED", "DISPUTED"},
    "COLLECTED": {"WEIGHED", "DISPUTED"},
    "WEIGHED": {"PROCESSING", "COMPLETED", "DISPUTED"},
    "PROCESSING": {"COMPLETED", "DISPUTED"},
}


def listing_view(db: Session, item: WasteListing, user: User) -> dict:
    roles = {r.role_code for r in user.roles}
    own = user.id == item.owner_id
    accepted_recycler = "RECYCLER" in roles and db.scalar(select(CollectionRequest.id).where(CollectionRequest.listing_id == item.id, CollectionRequest.recycler_id == user.id, CollectionRequest.status != "CANCELLED")) is not None
    count = db.scalar(select(func.count(RecyclerOffer.id)).where(RecyclerOffer.listing_id == item.id)) or 0
    return {
        "id": str(item.id), "is_mine": own, "category_code": item.category_code,
        "quantity_grams": item.quantity_grams, "condition": item.condition, "description": item.description,
        "status": item.status, "created_at": item.created_at.isoformat(), "offer_count": count,
        "pickup_address": item.pickup_address if own or accepted_recycler else None,
        "location": {"latitude": item.latitude, "longitude": item.longitude} if own or accepted_recycler else None,
    }


def offer_view(item: RecyclerOffer) -> dict:
    return {"id": str(item.id), "listing_id": str(item.listing_id), "recycler_id": str(item.recycler_id), "price_minor_per_kg": item.price_minor_per_kg, "pickup_fee_minor": item.pickup_fee_minor, "proposed_pickup_at": item.proposed_pickup_at.isoformat() if item.proposed_pickup_at else None, "expires_at": item.expires_at.isoformat() if item.expires_at else None, "notes": item.notes, "status": item.status, "created_at": item.created_at.isoformat()}


def collection_view(db: Session, row: CollectionRequest, user: User) -> dict:
    return {
        "id": str(row.id), "listing_id": str(row.listing_id), "offer_id": str(row.offer_id),
        "user_id": str(row.user_id), "recycler_id": str(row.recycler_id),
        "estimated_quantity_grams": row.estimated_quantity_grams, "actual_quantity_grams": row.actual_quantity_grams,
        "status": row.status, "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
        "collected_at": row.collected_at.isoformat() if row.collected_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "listing": listing_view(db, db.get(WasteListing, row.listing_id), user),
        "history": [{"from_status": e.from_status, "to_status": e.to_status, "reason": e.reason, "created_at": e.created_at.isoformat()} for e in db.scalars(select(CollectionStatusHistory).where(CollectionStatusHistory.collection_id == row.id).order_by(CollectionStatusHistory.created_at))],
    }


@router.get("/listings")
def get_listings(category: str | None = None, state: str = Query(default="OPEN", alias="status"), limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    query = select(WasteListing).where(WasteListing.status == state)
    if category:
        query = query.where(WasteListing.category_code == category)
    if state != "OPEN":
        query = query.where(WasteListing.owner_id == user.id)
    rows = db.scalars(query.order_by(WasteListing.created_at.desc()).limit(limit).offset(offset)).all()
    return [listing_view(db, row, user) for row in rows]


@router.post("/listings", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def create_listing(payload: ListingCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    category = db.get(WasteCategory, payload.category_code)
    if category is None or not category.is_active:
        raise HTTPException(422, "Choose an available waste category")
    if payload.classification_id:
        classification = db.scalar(select(WasteClassification).where(WasteClassification.id == payload.classification_id, WasteClassification.user_id == user.id))
        if classification is None:
            raise HTTPException(404, "Classification not found")
    item = WasteListing(owner_id=user.id, classification_id=payload.classification_id, category_code=payload.category_code, quantity_grams=payload.quantity_grams, condition=payload.condition, description=payload.description, pickup_address=payload.pickup_address, latitude=payload.location.latitude, longitude=payload.location.longitude, preferred_start=payload.preferred_start, preferred_end=payload.preferred_end)
    db.add(item)
    db.flush()
    record_audit(db, user.id, "LISTING_CREATED", "waste_listing", item.id, {"category_code": item.category_code, "quantity_grams": item.quantity_grams})
    db.commit()
    db.refresh(item)
    return listing_view(db, item, user)


@router.get("/listings/{listing_id}")
def get_listing(listing_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    item = db.get(WasteListing, listing_id)
    if item is None:
        raise HTTPException(404, "Listing not found")
    return listing_view(db, item, user)


@router.post("/listings/{listing_id}/offers", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def submit_offer(listing_id: UUID, payload: OfferCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER"))) -> dict:
    item = db.scalar(select(WasteListing).where(WasteListing.id == listing_id).with_for_update())
    if item is None or item.status != "OPEN":
        raise HTTPException(404, "Open listing not found")
    if item.owner_id == user.id:
        raise HTTPException(409, "You cannot offer on your own listing")
    profile = db.get(RecyclerProfile, user.id)
    accepted = db.scalar(select(RecyclerAcceptedCategory).where(RecyclerAcceptedCategory.recycler_id == user.id, RecyclerAcceptedCategory.category_code == item.category_code))
    if profile is None or accepted is None:
        raise HTTPException(409, "Your recycler profile does not accept this material")
    if item.quantity_grams < profile.min_pickup_grams or (profile.max_capacity_grams is not None and item.quantity_grams > profile.max_capacity_grams):
        raise HTTPException(409, "Listing quantity is outside your pickup limits")
    areas = db.scalars(select(RecyclerServiceArea).where(RecyclerServiceArea.recycler_id == user.id)).all()
    if not areas or not any(meters_between(a.center_latitude, a.center_longitude, item.latitude, item.longitude) <= a.radius_meters for a in areas):
        raise HTTPException(409, "Pickup is outside your configured service area (preliminary straight-line check)")
    offer = RecyclerOffer(listing_id=item.id, recycler_id=user.id, price_minor_per_kg=payload.price_minor_per_kg, pickup_fee_minor=payload.pickup_fee_minor, proposed_pickup_at=payload.proposed_pickup_at, expires_at=payload.expires_at, notes=payload.notes)
    db.add(offer)
    db.add(Notification(user_id=item.owner_id, event_type="OFFER_RECEIVED", title="A recycler made an offer", body=f"A recycler submitted an offer for your {item.category_code} listing."))
    db.flush()
    record_audit(db, user.id, "OFFER_SUBMITTED", "recycler_offer", offer.id, {"listing_id": str(item.id), "price_minor_per_kg": offer.price_minor_per_kg, "pickup_fee_minor": offer.pickup_fee_minor})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "You have already submitted an offer for this listing") from None
    db.refresh(offer)
    return offer_view(offer)


@router.get("/listings/{listing_id}/offers")
def listing_offers(listing_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    item = db.get(WasteListing, listing_id)
    if item is None:
        raise HTTPException(404, "Listing not found")
    if item.owner_id != user.id and "ADMIN" not in {role.role_code for role in user.roles}:
        own_offers = db.scalars(select(RecyclerOffer).where(RecyclerOffer.listing_id == listing_id, RecyclerOffer.recycler_id == user.id)).all()
        return [offer_view(offer) for offer in own_offers]
    offers = db.scalars(select(RecyclerOffer).where(RecyclerOffer.listing_id == listing_id).order_by(RecyclerOffer.created_at)).all()
    return [offer_view(offer) for offer in offers]


@router.post("/offers/{offer_id}/accept", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def accept_offer(offer_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    offer = db.scalar(select(RecyclerOffer).where(RecyclerOffer.id == offer_id).with_for_update())
    if offer is None:
        raise HTTPException(404, "Offer not found")
    item = db.scalar(select(WasteListing).where(WasteListing.id == offer.listing_id).with_for_update())
    if item is None or item.owner_id != user.id:
        raise HTTPException(404, "Offer not found")
    if item.status != "OPEN" or offer.status != "SUBMITTED":
        raise HTTPException(409, "This listing or offer is no longer available")
    if offer.expires_at and offer.expires_at <= datetime.now(UTC):
        offer.status = "EXPIRED"
        db.commit()
        raise HTTPException(409, "Offer has expired")
    offer.status = "ACCEPTED"
    others = db.scalars(select(RecyclerOffer).where(RecyclerOffer.listing_id == item.id, RecyclerOffer.id != offer.id, RecyclerOffer.status == "SUBMITTED")).all()
    for other in others:
        other.status = "REJECTED"
    item.status = "ACCEPTED"
    collection = CollectionRequest(listing_id=item.id, offer_id=offer.id, user_id=user.id, recycler_id=offer.recycler_id, estimated_quantity_grams=item.quantity_grams, status="ACCEPTED")
    db.add(collection)
    db.flush()
    db.add(CollectionStatusHistory(collection_id=collection.id, actor_id=user.id, from_status=None, to_status="ACCEPTED", reason="Offer accepted"))
    db.add(Notification(user_id=offer.recycler_id, event_type="OFFER_ACCEPTED", title="Your offer was accepted", body="The household accepted your collection offer.", collection_id=collection.id))
    record_audit(db, user.id, "OFFER_ACCEPTED", "collection_request", collection.id, {"listing_id": str(item.id), "offer_id": str(offer.id), "recycler_id": str(offer.recycler_id)})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Another offer has already been accepted for this listing") from None
    return collection_view(db, collection, user)


@router.get("/collections")
def get_collections(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    roles = {row.role_code for row in user.roles}
    query = select(CollectionRequest)
    if "ADMIN" not in roles:
        query = query.where((CollectionRequest.user_id == user.id) | ((CollectionRequest.recycler_id == user.id) if "RECYCLER" in roles else False))
    rows = db.scalars(query.order_by(CollectionRequest.created_at.desc()).limit(100)).all()
    return [collection_view(db, row, user) for row in rows]


@router.get("/collections/{collection_id}")
def get_collection(collection_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    row = db.get(CollectionRequest, collection_id)
    if row is None or (row.user_id != user.id and row.recycler_id != user.id and "ADMIN" not in {role.role_code for role in user.roles}):
        raise HTTPException(404, "Collection not found")
    return collection_view(db, row, user)


@router.post("/collections/{collection_id}/transition", dependencies=[Depends(require_csrf)])
def transition_collection(collection_id: UUID, payload: TransitionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    row = db.scalar(select(CollectionRequest).where(CollectionRequest.id == collection_id).with_for_update())
    roles = {role.role_code for role in user.roles}
    if row is None or (row.user_id != user.id and row.recycler_id != user.id and "ADMIN" not in roles):
        raise HTTPException(404, "Collection not found")
    target = payload.status.upper()
    if target not in TRANSITIONS.get(row.status, set()):
        raise HTTPException(409, f"Transition from {row.status} to {target} is not allowed")
    is_recycler = user.id == row.recycler_id or "ADMIN" in roles
    is_owner = user.id == row.user_id or "ADMIN" in roles
    if target in {"EN_ROUTE", "ARRIVED", "COLLECTED", "WEIGHED", "PROCESSING", "COMPLETED"} and not is_recycler:
        raise HTTPException(403, "Only the assigned recycler can update collection progress")
    if target == "SCHEDULED" and payload.scheduled_at is None:
        raise HTTPException(422, "A scheduled pickup time is required")
    if target == "WEIGHED" and payload.actual_quantity_grams is None:
        raise HTTPException(422, "Record the actual collected quantity in grams")
    if target == "COMPLETED" and row.actual_quantity_grams is None:
        raise HTTPException(409, "Record a verified collected quantity before completing")
    if target == "CANCELLED" and not (is_owner or is_recycler):
        raise HTTPException(403, "Only the collection participants can cancel")
    if target == "DISPUTED" and not (is_owner or is_recycler):
        raise HTTPException(403, "Only the collection participants can raise a dispute")
    previous = row.status
    row.status = target
    if target == "SCHEDULED":
        row.scheduled_at = payload.scheduled_at
    if target == "COLLECTED":
        row.collected_at = datetime.now(UTC)
    if target == "WEIGHED":
        row.actual_quantity_grams = payload.actual_quantity_grams
    if target == "COMPLETED":
        row.completed_at = datetime.now(UTC)
        db.get(WasteListing, row.listing_id).status = "CLOSED"
    if target == "CANCELLED":
        row.cancellation_reason = payload.reason
        db.get(WasteListing, row.listing_id).status = "CANCELLED"
    db.add(CollectionStatusHistory(collection_id=row.id, actor_id=user.id, from_status=previous, to_status=target, reason=payload.reason))
    recipient = row.recycler_id if user.id == row.user_id else row.user_id
    db.add(Notification(user_id=recipient, event_type=f"COLLECTION_{target}", title=f"Collection {target.lower().replace('_',' ')}", body=payload.reason or f"Collection status changed to {target.lower().replace('_',' ')}.", collection_id=row.id))
    record_audit(db, user.id, "COLLECTION_TRANSITIONED", "collection_request", row.id, {"from_status": previous, "to_status": target, "actual_quantity_grams": row.actual_quantity_grams})
    db.commit()
    db.refresh(row)
    return collection_view(db, row, user)


@router.get("/notifications")
def get_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(100)).all()
    return [{"id": str(n.id), "event_type": n.event_type, "title": n.title, "body": n.body, "collection_id": str(n.collection_id) if n.collection_id else None, "is_read": n.is_read, "created_at": n.created_at.isoformat()} for n in rows]
