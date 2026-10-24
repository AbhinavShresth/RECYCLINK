from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request

_attempts: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = Lock()


def rate_limit(scope: str, max_requests: int, window_seconds: int):
    """Small-process development limiter; production multi-worker deployments need shared storage."""

    def dependency(request: Request) -> None:
        host = request.client.host if request.client else "unknown"
        key = (scope, host)
        now = monotonic()
        cutoff = now - window_seconds
        with _lock:
            events = _attempts[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= max_requests:
                retry_after = max(1, int(window_seconds - (now - events[0])))
                raise HTTPException(429, "Too many requests; please try again later", headers={"Retry-After": str(retry_after)})
            events.append(now)

    return dependency
