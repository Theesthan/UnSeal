"""FastAPI app factory: wiring only. Business logic lives in services/, harness/ and rules/.

Dependencies are injected (session factory, model client, PDF renderer) so tests use fakes and
nothing reaches BharatCode or the network unless a live test asks for it.
"""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from unseal.api import cases, errors, session
from unseal.api.deps import SESSION_COOKIE
from unseal.api.ratelimit import RateLimits
from unseal.config import Settings
from unseal.db.session import build_engine, build_session_factory
from unseal.privacy.redact import install_redaction

__all__ = ["SESSION_COOKIE", "create_app"]

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_SECRET_HEADER_PATHS = frozenset({"/telegram/webhook"})  # checked by its own secret header

Next = Callable[[Request], Awaitable[Response]]


def create_app(
    settings: Settings,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    llm: Any = None,
    renderer: Any = None,
) -> FastAPI:
    factory = session_factory or build_session_factory(
        build_engine(settings.database_url.get_secret_value())
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        install_redaction()
        for name in ("uvicorn.error", "uvicorn.access"):  # they do not propagate to root
            install_redaction(logging.getLogger(name))
        yield

    app = FastAPI(title="UnSeal API", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = factory
    app.state.llm = llm
    app.state.renderer = renderer
    app.state.rate_limits = RateLimits(settings.rate_limit_default, settings.rate_limit_model)

    errors.install(app)
    app.include_router(session.router)
    app.include_router(cases.router)

    @app.middleware("http")
    async def require_app_origin(request: Request, call_next: Next) -> Response:
        """Cookie-authenticated writes must come from the web app (ADR 0003, CSRF)."""
        checked = (
            request.method not in _SAFE_METHODS and request.url.path not in _SECRET_HEADER_PATHS
        )
        if checked and request.headers.get("origin") != settings.app_base_url:
            return errors.error_response(403, "bad_origin")
        return await call_next(request)

    @app.middleware("http")
    async def rate_limit(request: Request, call_next: Next) -> Response:
        if request.method != "OPTIONS" and not app.state.rate_limits.allow(request):
            return errors.error_response(429, "rate_limited")
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,  # outermost, so even 403 and 429 answers carry CORS headers
        allow_origins=[settings.app_base_url],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )
    return app
