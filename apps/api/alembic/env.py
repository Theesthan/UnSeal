"""Alembic environment: async engine, URL from the application settings (never from alembic.ini)."""

import asyncio
from logging.config import fileConfig
from typing import Any

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.types import TypeDecorator

from alembic import context
from unseal.config import DatabaseSettings
from unseal.db.models import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def database_url() -> str:
    return DatabaseSettings().database_url.get_secret_value()


def render_item(type_: str, obj: Any, autogen_context: Any) -> str | bool:
    """Render our TypeDecorators as the plain SQLAlchemy type they store as, so generated
    migrations never import application code."""
    if type_ == "type" and isinstance(obj, TypeDecorator):
        return f"sa.{obj.impl!r}"
    return False


def run_migrations_offline() -> None:
    """Emit SQL without connecting (`alembic upgrade head --sql`)."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=True,  # SQLite cannot ALTER most things in place
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(database_url(), poolclass=pool.NullPool, hide_parameters=True)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
