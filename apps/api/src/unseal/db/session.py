"""Async engine and session factory, built from settings.

`get_session` is the FastAPI dependency. It never commits for you: the service layer commits, and a
request that ends without a commit has its work rolled back.
"""

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from unseal.config import DatabaseSettings


def _enable_sqlite_foreign_keys(engine: AsyncEngine) -> None:
    """SQLite ignores foreign keys (and so ON DELETE CASCADE) unless asked, per connection."""
    if engine.dialect.name != "sqlite":
        return

    def _pragma(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(engine.sync_engine, "connect", _pragma)


def build_engine(database_url: str) -> AsyncEngine:
    """An async engine for an async-driver URL (for example `sqlite+aiosqlite:///./dev.db`).

    `hide_parameters` keeps bound values out of exception text: SQLAlchemy would otherwise print
    "[parameters: ...]" into tracebacks and logs, and those can be personal data.
    """
    engine = create_async_engine(database_url, hide_parameters=True, pool_pre_ping=True)
    _enable_sqlite_foreign_keys(engine)
    return engine


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: async code cannot lazily refresh an expired object.
    return async_sessionmaker(engine, expire_on_commit=False)


def _load_database_url() -> str:
    return DatabaseSettings().database_url.get_secret_value()


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """The process-wide engine, created on first use from DATABASE_URL."""
    return build_engine(_load_database_url())


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return build_session_factory(get_engine())


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, closed (and rolled back if uncommitted)."""
    async with get_session_factory()() as session:
        yield session


async def dispose_engine() -> None:
    """Close pooled connections (app shutdown) and forget the cached engine."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
