import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_csrf, require_roles
from app.core.config import get_settings
from app.db.session import get_db
from app.models.identity import User
from app.models.marketplace import CollectionRequest, RoutePlan, RouteStop, WasteListing
from app.routing.optimizer import optimize, route_cost
from app.routing.osrm import OSRMProvider, Point, RoutingUnavailable
from app.schemas.routes import OptimizeRouteIn

router = APIRouter(prefix="/routes", tags=["routing"])


def view_route(db: Session, route: RoutePlan) -> dict:
    stops = db.scalars(select(RouteStop).where(RouteStop.route_id == route.id).order_by(RouteStop.sequence)).all()
    collections = []
    for stop in stops:
        collection = db.get(CollectionRequest, stop.collection_id)
        listing = db.get(WasteListing, collection.listing_id)
        collections.append({"sequence": stop.sequence, "collection_id": str(collection.id), "category_code": listing.category_code, "quantity_grams": listing.quantity_grams})
    return {
        "id": str(route.id), "recycler_id": str(route.recycler_id), "router": "OSRM-compatible road router",
        "geometry": {"type": "LineString", "coordinates": json.loads(route.geometry_json)}, "stops": collections,
        "baseline_distance_meters": route.baseline_distance_meters, "optimized_distance_meters": route.optimized_distance_meters,
        "baseline_duration_seconds": route.baseline_duration_seconds, "optimized_duration_seconds": route.optimized_duration_seconds,
        "distance_saved_percentage": route.distance_saved_percentage, "duration_saved_percentage": route.duration_saved_percentage,
        "method": route.method, "router_data_version": route.router_data_version, "created_at": route.created_at.isoformat(),
        "constraints_note": "Vehicle capacity and pickup time-window constraints are not supported by this prototype optimizer.",
    }


@router.post("/optimize", status_code=status.HTTP_201_CREATED)
def optimize_route(payload: OptimizeRouteIn, db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER")), _: None = Depends(require_csrf)) -> dict:
    settings = get_settings()
    if not settings.osrm_base_url:
        raise HTTPException(503, "Road routing is not configured. Set OSRM_BASE_URL to an approved OSRM-compatible service.")
    if len(set(payload.stop_collection_ids)) != len(payload.stop_collection_ids):
        raise HTTPException(422, "A collection can appear only once in a route")
    rows = db.scalars(select(CollectionRequest).where(CollectionRequest.id.in_(payload.stop_collection_ids), CollectionRequest.recycler_id == user.id, CollectionRequest.status.in_(["ACCEPTED", "SCHEDULED", "ASSIGNED"]))).all()
    by_id = {row.id: row for row in rows}
    if len(by_id) != len(payload.stop_collection_ids):
        raise HTTPException(404, "One or more selected active collections are unavailable to this recycler")
    ordered_rows = [by_id[collection_id] for collection_id in payload.stop_collection_ids]
    start = Point(payload.start.latitude, payload.start.longitude)
    end = Point(payload.end.latitude, payload.end.longitude) if payload.end else start
    stops = [Point(db.get(WasteListing, row.listing_id).latitude, db.get(WasteListing, row.listing_id).longitude) for row in ordered_rows]
    points = [start, *stops, end]
    provider = OSRMProvider(settings.osrm_base_url, timeout=settings.route_timeout_seconds)
    try:
        matrix_response = provider.table(points)
        matrix = matrix_response["durations"]
        result = optimize(matrix, len(stops))
        baseline_distance = route_cost([0, *range(1, len(stops) + 1), len(stops) + 1], matrix_response["distances"])
        ordered_points = [points[index] for index in result["optimized_order"]]
        geometry_result = provider.route(ordered_points)
    except ValueError as exc:
        raise HTTPException(502, str(exc)) from None
    except RoutingUnavailable as exc:
        raise HTTPException(503, str(exc)) from None
    optimized_duration = geometry_result["duration_seconds"]
    baseline_duration = result["baseline_duration_seconds"]
    distance_percentage = ((baseline_distance - geometry_result["distance_meters"]) / baseline_distance * 100) if baseline_distance > 0 else None
    time_percentage = ((baseline_duration - optimized_duration) / baseline_duration * 100) if baseline_duration > 0 else None
    route = RoutePlan(
        recycler_id=user.id, start_latitude=start.latitude, start_longitude=start.longitude,
        end_latitude=end.latitude, end_longitude=end.longitude, baseline_distance_meters=baseline_distance,
        optimized_distance_meters=geometry_result["distance_meters"], baseline_duration_seconds=baseline_duration,
        optimized_duration_seconds=optimized_duration, distance_saved_percentage=distance_percentage,
        duration_saved_percentage=time_percentage, geometry_json=json.dumps(geometry_result["geometry"]),
        router_data_version=matrix_response.get("data_version"), method=result["method"],
    )
    db.add(route)
    db.flush()
    for sequence, point_index in enumerate(result["optimized_order"][1:-1], start=1):
        db.add(RouteStop(route_id=route.id, collection_id=ordered_rows[point_index - 1].id, sequence=sequence))
    db.commit()
    db.refresh(route)
    return view_route(db, route)


@router.get("")
def list_routes(db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER"))) -> list[dict]:
    rows = db.scalars(select(RoutePlan).where(RoutePlan.recycler_id == user.id).order_by(RoutePlan.created_at.desc()).limit(50)).all()
    return [view_route(db, route) for route in rows]


@router.get("/{route_id}")
def get_route(route_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER"))) -> dict:
    route = db.scalar(select(RoutePlan).where(RoutePlan.id == route_id, RoutePlan.recycler_id == user.id))
    if route is None:
        raise HTTPException(404, "Route plan not found")
    return view_route(db, route)
