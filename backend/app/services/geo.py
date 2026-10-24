from math import asin, cos, radians, sin, sqrt


def meters_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance for proximity prefiltering, never a road distance."""
    p1, p2 = radians(lat1), radians(lat2)
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    value = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    return 6_371_000 * 2 * asin(sqrt(value))
