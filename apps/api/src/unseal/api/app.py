"""FastAPI app factory: wiring only. Business logic lives in services/, harness/ and rules/.

Dependencies are injected (session factory, model client, PDF renderer) so tests use fakes and
nothing reaches BharatCode or the network unless a live test asks for it.
"""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from unseal import scheduler
from unseal.api import cases, errors, reference, session, telegram
from unseal.api.deps import SESSION_COOKIE
from unseal.api.ratelimit import RateLimits
from unseal.config import Settings
from unseal.db.session import build_engine, build_session_factory
from unseal.pdf.render import render_application_pdf
from unseal.privacy.redact import install_redaction

__all__ = ["SESSION_COOKIE", "create_app"]

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_SECRET_HEADER_PATHS = frozenset({"/telegram/webhook"})  # checked by its own secret header

Next = Callable[[Request], Awaitable[Response]]

TICK_MINUTES = 15  # CLAUDE.md: the reminder job runs every 15 minutes
FIRST_TICK_SECONDS = 30  # the first run comes shortly after start, not 15 minutes later


def start_jobs(app: FastAPI) -> AsyncIOScheduler:
    """`scheduler.tick` (deemed refusals, retention, FR-9 reminders) every TICK_MINUTES. Reminders
    go out on Telegram when the bot is running; without it the sender is None and nothing is
    claimed, so no reminder is lost. ponytail: one scheduler per process; with several API
    replicas each runs ticks, which the claim-before-send markers keep safe but wasteful."""
    settings: Settings = app.state.settings
    send = telegram.reminder_sender(app)

    async def run_tick() -> None:
        await scheduler.tick(
            app.state.session_factory,
            storage_dir=settings.storage_dir,
            now=datetime.now(UTC),
            send=send,
        )

    jobs = AsyncIOScheduler(timezone=UTC)
    jobs.add_job(
        run_tick,
        "interval",
        minutes=TICK_MINUTES,
        id="tick",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(UTC) + timedelta(seconds=FIRST_TICK_SECONDS),
    )
    jobs.start()
    return jobs


def create_app(
    settings: Settings,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    llm: Any = None,
    renderer: Any = None,
    run_scheduler: bool = True,
) -> FastAPI:
    factory = session_factory or build_session_factory(
        build_engine(settings.database_url.get_secret_value())
    )

    @asynccontextmanager
    async def lifespan(api: FastAPI) -> AsyncIterator[None]:
        install_redaction()
        for name in ("uvicorn.error", "uvicorn.access"):  # they do not propagate to root
            install_redaction(logging.getLogger(name))
        await telegram.start_bot(api)  # webhook mode; off unless TELEGRAM_BOT_TOKEN is set
        api.state.jobs = start_jobs(api) if run_scheduler else None
        try:
            yield
        finally:
            if api.state.jobs is not None:
                api.state.jobs.shutdown(wait=False)  # before the bot stops: no tick sends late
            await telegram.stop_bot(api)

    app = FastAPI(title="UnSeal API", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = factory
    app.state.llm = llm
    app.state.renderer = renderer or render_application_pdf
    app.state.rate_limits = RateLimits(settings.rate_limit_default, settings.rate_limit_model)

    errors.install(app)
    app.include_router(session.router)
    app.include_router(cases.router)
    app.include_router(reference.router)
    app.include_router(telegram.router)

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
