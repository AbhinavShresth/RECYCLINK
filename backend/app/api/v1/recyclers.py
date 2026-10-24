from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user, require_csrf, require_roles
from app.db.session import get_db
from app.models.identity import (
    RecyclerAcceptedCategory,
    RecyclerProfile,
    RecyclerServiceArea,
    User,
    WasteCategory,
)
from app.schemas.recycler import RecyclerProfileIn, RecyclerProfileOut
from app.services.geo import meters_between

router = APIRouter(prefix="/recyclers", tags=["recyclers"])


@router.get("/discover")
def discover_recyclers(category: str = Query(min_length=1, max_length=32), latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180), quantity_grams: int = Query(gt=0), db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    profiles = db.scalars(select(RecyclerProfile).options(selectinload(RecyclerProfile.service_areas), selectinload(RecyclerProfile.accepted_categories))).all()
    matches = []
    for profile in profiles:
        accepted = next((row for row in profile.accepted_categories if row.category_code == category), None)
        if accepted is None or quantity_grams < profile.min_pickup_grams or (profile.max_capacity_grams and quantity_grams > profile.max_capacity_grams):
            continue
        distances = [meters_between(latitude, longitude, area.center_latitude, area.center_longitude) for area in profile.service_areas if meters_between(latitude, longitude, area.center_latitude, area.center_longitude) <= area.radius_meters]
        if not distances:
            continue
        matches.append({"business_name": profile.business_name, "description": profile.description, "verified": profile.verified_at is not None, "category_code": category, "indicative_price_minor_per_kg": accepted.indicative_price_minor_per_kg, "currency": accepted.currency, "minimum_pickup_grams": profile.min_pickup_grams, "straight_line_distance_meters": round(min(distances)), "distance_metric": "STRAIGHT_LINE_SERVICE_AREA_FILTER", "service_area_match": True})
    return sorted(matches, key=lambda item: (item["straight_line_distance_meters"], item["indicative_price_minor_per_kg"] is None, item["indicative_price_minor_per_kg"] or 0))[:50]


@router.get("/me", response_model=RecyclerProfileOut)
def get_my_recycler_profile(
    user: User = Depends(require_roles("RECYCLER")), db: Session = Depends(get_db)
) -> RecyclerProfile:
    profile = db.scalar(
        select(RecyclerProfile)
        .options(selectinload(RecyclerProfile.service_areas), selectinload(RecyclerProfile.accepted_categories))
        .where(RecyclerProfile.user_id == user.id)
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Recycler profile has not been created")
    return profile


@router.put("/me", response_model=RecyclerProfileOut, dependencies=[Depends(require_csrf)])
def upsert_my_recycler_profile(
    payload: RecyclerProfileIn,
    user: User = Depends(require_roles("RECYCLER")),
    db: Session = Depends(get_db),
) -> RecyclerProfile:
    category_codes = [entry.category_code for entry in payload.accepted_categories]
    if len(set(category_codes)) != len(category_codes):
        raise HTTPException(status_code=422, detail="Accepted categories must not contain duplicates")
    known = set(db.scalars(select(WasteCategory.code).where(WasteCategory.code.in_(category_codes))))
    if known != set(category_codes):
        raise HTTPException(status_code=422, detail="One or more waste categories are unknown")
    profile = db.get(RecyclerProfile, user.id)
    if profile is None:
        profile = RecyclerProfile(user_id=user.id, business_name=payload.business_name)
        db.add(profile)
    profile.business_name = payload.business_name
    profile.description = payload.description
    profile.phone_public = payload.phone_public
    profile.min_pickup_grams = payload.min_pickup_grams
    profile.max_capacity_grams = payload.max_capacity_grams
    profile.service_areas.clear()
    profile.service_areas.extend(RecyclerServiceArea(**area.model_dump()) for area in payload.service_areas)
    profile.accepted_categories.clear()
    profile.accepted_categories.extend(RecyclerAcceptedCategory(**category.model_dump()) for category in payload.accepted_categories)
    db.commit()
    return db.scalar(
        select(RecyclerProfile)
        .options(selectinload(RecyclerProfile.service_areas), selectinload(RecyclerProfile.accepted_categories))
        .where(RecyclerProfile.user_id == user.id)
    )
