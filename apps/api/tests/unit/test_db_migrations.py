"""Alembic: the initial migration builds exactly the schema the models describe, and reverses.

These tests are synchronous on purpose: alembic's async env.py calls asyncio.run, which cannot
run inside a pytest-anyio event loop.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint

from alembic import command
from unseal.db.models import Base

API_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI = API_DIR / "alembic.ini"
TABLES = {"users", "applicants", "cases", "questions", "deadlines", "documents"}


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    """Commit on success and always close: an open handle would lock the file on Windows."""
    conn = sqlite3.connect(path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    config.attributes["configure_logger"] = False  # keep pytest's logging capture intact
    return config


@pytest.fixture
def db_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fresh SQLite file that alembic reaches through DATABASE_URL, as in real use."""
    path = tmp_path / "migrated.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path.as_posix()}")
    return path


def table_names(path: Path) -> set[str]:
    with connect(path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {name for (name,) in rows}


def test_there_is_a_single_linear_history_starting_at_0001() -> None:
    script = ScriptDirectory.from_config(alembic_config())
    assert script.get_heads() == ["0001"]
    revision = script.get_revision("0001")
    assert revision is not None
    assert revision.down_revision is None


def test_upgrade_head_creates_every_table(db_file: Path) -> None:
    assert not db_file.exists()
    command.upgrade(alembic_config(), "head")
    assert table_names(db_file) == TABLES | {"alembic_version"}


def test_upgrade_is_repeatable(db_file: Path) -> None:
    command.upgrade(alembic_config(), "head")
    command.upgrade(alembic_config(), "head")
    assert table_names(db_file) == TABLES | {"alembic_version"}


def test_migrated_schema_matches_the_models(db_file: Path) -> None:
    command.upgrade(alembic_config(), "head")
    engine = sa.create_engine(f"sqlite:///{db_file.as_posix()}")
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection, opts={"compare_type": True, "compare_server_default": True}
            )
            assert compare_metadata(context, Base.metadata) == []
    finally:
        engine.dispose()


def test_comparison_would_notice_drift(db_file: Path) -> None:
    # Guard against a vacuous check: a column added behind alembic's back must show up.
    command.upgrade(alembic_config(), "head")
    with connect(db_file) as conn:
        conn.execute("ALTER TABLE cases ADD COLUMN rogue TEXT")
    engine = sa.create_engine(f"sqlite:///{db_file.as_posix()}")
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()
    assert diff
    assert any("rogue" in repr(item) for item in diff)


def test_check_constraints_are_in_the_migrated_tables(db_file: Path) -> None:
    # Alembic's comparison does not look at CHECK constraints, so assert them directly:
    # same names and same SQL as the models declare.
    command.upgrade(alembic_config(), "head")
    with connect(db_file) as conn:
        ddl = {
            name: sql
            for name, sql in conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type = 'table'"
            )
        }
    expected = 0
    for table in Base.metadata.sorted_tables:
        for constraint in table.constraints:
            if isinstance(constraint, CheckConstraint):
                expected += 1
                assert f"CONSTRAINT {constraint.name}" in ddl[table.name]
                assert str(constraint.sqltext) in ddl[table.name]
    assert expected == 6


def test_migrated_database_rejects_bad_values_and_cascades(db_file: Path) -> None:
    command.upgrade(alembic_config(), "head")
    with connect(db_file) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "INSERT INTO users (id, channel, language, created_at)"
            " VALUES ('u', 'web', 'en', '2026-01-01 00:00:00')"
        )
        conn.execute("INSERT INTO applicants (id, user_id, name) VALUES ('a', 'u', 'x')")
        with pytest.raises(sqlite3.IntegrityError, match="ck_cases_status"):
            conn.execute(
                "INSERT INTO cases (id, user_id, applicant_id, jurisdiction, status, via_apio,"
                " third_party, life_liberty, language, created_at) VALUES"
                " ('c', 'u', 'a', 'central', 'bogus', 0, 0, 0, 'en', '2026-01-01 00:00:00')"
            )
        conn.execute(
            "INSERT INTO cases (id, user_id, applicant_id, jurisdiction, status, via_apio,"
            " third_party, life_liberty, language, created_at) VALUES"
            " ('c', 'u', 'a', 'central', 'draft', 0, 0, 0, 'en', '2026-01-01 00:00:00')"
        )
        conn.execute(
            "INSERT INTO deadlines (id, case_id, kind, due_on, estimated) VALUES"
            " ('d', 'c', 'pio_reply', '2026-12-01', 0)"
        )
        conn.execute("DELETE FROM users WHERE id = 'u'")
        for table in TABLES:
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)


def test_downgrade_removes_everything_it_created(db_file: Path) -> None:
    command.upgrade(alembic_config(), "head")
    command.downgrade(alembic_config(), "base")
    assert table_names(db_file) == {"alembic_version"}


def test_downgrade_refuses_to_drop_tables_that_hold_data(db_file: Path) -> None:
    command.upgrade(alembic_config(), "head")
    with connect(db_file) as conn:
        conn.execute(
            "INSERT INTO users (id, channel, language, created_at)"
            " VALUES ('u', 'web', 'en', '2026-01-01 00:00:00')"
        )
    with pytest.raises(RuntimeError, match="holds data"):
        command.downgrade(alembic_config(), "base")
    assert table_names(db_file) == TABLES | {"alembic_version"}
    with connect(db_file) as conn:
        assert conn.execute("SELECT count(*) FROM users").fetchone() == (1,)


def test_autogenerate_renders_portable_types_without_importing_app_code(
    db_file: Path, tmp_path: Path
) -> None:
    # A migration must never import unseal.* (the class could change or move later).
    # Point alembic at an empty versions folder so autogenerate emits the whole schema.
    versions = tmp_path / "versions"
    versions.mkdir()
    config = alembic_config()
    config.set_main_option("version_locations", str(versions))
    command.revision(config, message="draft", autogenerate=True, rev_id="draft")
    (script,) = versions.glob("*.py")
    text = script.read_text(encoding="utf-8")
    assert "unseal" not in text
    assert "sa.Text()" in text
    assert "sa.DateTime(timezone=True)" in text
