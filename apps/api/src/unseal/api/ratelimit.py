"""Per-session rate limits (CLAUDE.md security checklist), on the `limits` library directly.

slowapi's middleware cannot match FastAPI routes in the version we use and silently exempted
every request, so this module does the two things we need: a default limit on every request and a
stricter quota on routes that call BharatCode (the shared 10M-token daily cap is a DoS target).
ponytail: in-memory storage, so limits are per process; move to Redis if the API scales out.
"""

import hashlib
from typing import Annotated

from fastapi import Depends, Request
from limits import RateLimitItem, parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from unseal.api.deps import SESSION_COOKIE
from unseal.api.errors import ApiError


def rate_key(request: Request) -> str:
    """Per session when there is one (hashed: the raw token never enters limiter storage)."""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        return "s:" + hashlib.sha256(token.encode()).hexdigest()
    return "ip:" + (request.client.host if request.client else "unknown")


class RateLimits:
    def __init__(self, default: str, model: str) -> None:
        self._limiter = MovingWindowRateLimiter(MemoryStorage())
        self._default: RateLimitItem = parse(default)
        self._model: RateLimitItem = parse(model)

    def allow(self, request: Request) -> bool:
        return self._limiter.hit(self._default, rate_key(request), "default")

    def allow_model_call(self, request: Request) -> bool:
        return self._limiter.hit(self._model, rate_key(request), "model")


def model_quota(request: Request) -> None:
    """Route dependency for every endpoint that calls BharatCode."""
    limits: RateLimits = request.app.state.rate_limits
    if not limits.allow_model_call(request):
        raise ApiError(429, "rate_limited")


ModelQuota = Annotated[None, Depends(model_quota)]
