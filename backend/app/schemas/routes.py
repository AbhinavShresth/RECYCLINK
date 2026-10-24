from uuid import UUID

from pydantic import BaseModel, Field


class RoutePointIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class OptimizeRouteIn(BaseModel):
    start: RoutePointIn
    stop_collection_ids: list[UUID] = Field(min_length=1, max_length=12)
    end: RoutePointIn | None = None
