from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_csrf
from app.db.session import get_db
from app.models.identity import User, UserLocation
from app.schemas.identity import LocationCreate, LocationPublic

router = APIRouter(prefix="/users/me/locations", tags=["user locations"])


@router.get("", response_model=list[LocationPublic])
def list_locations(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[UserLocation]:
    return list(db.scalars(select(UserLocation).where(UserLocation.user_id == user.id).order_by(UserLocation.created_at.desc())))


@router.post("", response_model=LocationPublic, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def add_location(payload: LocationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserLocation:
    location = UserLocation(user_id=user.id, **payload.model_dump())
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
def delete_location(location_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    location = db.scalar(select(UserLocation).where(UserLocation.id == location_id, UserLocation.user_id == user.id))
    if location:
        db.delete(location)
        db.commit()
