from copy import deepcopy
from dataclasses import dataclass
from threading import Lock
from time import monotonic

import httpx


class RoutingUnavailable(Exception):
    pass


_cache: dict[tuple, tuple[float, dict]] = {}
_cache_lock = Lock()
_CACHE_TTL_SECONDS = 300
_CACHE_MAX_ITEMS = 128


def _request_json(base_url: str, path: str, params: dict, timeout: float) -> dict:
    key = (base_url, path, tuple(sorted(params.items())))
    now = monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and cached[0] > now:
            return deepcopy(cached[1])
    response = httpx.get(f"{base_url}{path}", params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX_ITEMS:
            oldest = min(_cache, key=lambda item: _cache[item][0])
            _cache.pop(oldest, None)
        _cache[key] = (now + _CACHE_TTL_SECONDS, payload)
    return payload


@dataclass(frozen=True)
class Point:
    latitude: float
    longitude: float


class OSRMProvider:
    def __init__(self, base_url: str, timeout: float = 8.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @staticmethod
    def _coords(points: list[Point]) -> str:
        return ";".join(f"{p.longitude:.6f},{p.latitude:.6f}" for p in points)

    def table(self, points: list[Point]) -> dict:
        try:
            payload = _request_json(self.base_url, f"/table/v1/driving/{self._coords(points)}", {"annotations": "distance,duration"}, self.timeout)
        except (httpx.HTTPError, ValueError):
            raise RoutingUnavailable("The road-routing provider could not be reached") from None
        if payload.get("code") != "Ok" or not payload.get("durations") or not payload.get("distances"):
            raise RoutingUnavailable("The road-routing provider could not build a complete distance matrix")
        if any(value is None for row in payload["durations"] for value in row) or any(value is None for row in payload["distances"] for value in row):
            raise RoutingUnavailable("One or more requested points cannot be routed on the road network")
        return {"durations": payload["durations"], "distances": payload["distances"], "data_version": payload.get("data_version")}

    def route(self, points: list[Point]) -> dict:
        try:
            payload = _request_json(self.base_url, f"/route/v1/driving/{self._coords(points)}", {"overview": "full", "geometries": "geojson", "steps": "false"}, self.timeout)
        except (httpx.HTTPError, ValueError):
            raise RoutingUnavailable("The road-routing provider could not return route geometry") from None
        if payload.get("code") != "Ok" or not payload.get("routes"):
            raise RoutingUnavailable("The road-routing provider found no road route for the selected stops")
        result = payload["routes"][0]
        geometry = result.get("geometry", {}).get("coordinates")
        if not geometry:
            raise RoutingUnavailable("The road-routing provider returned no route geometry")
        return {"distance_meters": result["distance"], "duration_seconds": result["duration"], "geometry": geometry}
