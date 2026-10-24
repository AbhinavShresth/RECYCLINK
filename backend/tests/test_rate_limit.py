from uuid import uuid4

import pytest
from fastapi import HTTPException, Request

from app.core.rate_limit import rate_limit


def test_process_rate_limit_returns_retry_after():
    request = Request({"type": "http", "client": ("127.0.0.1", 1234)})
    limiter = rate_limit(f"test-{uuid4()}", max_requests=1, window_seconds=30)
    limiter(request)
    with pytest.raises(HTTPException) as error:
        limiter(request)
    assert error.value.status_code == 429
    assert int(error.value.headers["Retry-After"]) > 0
