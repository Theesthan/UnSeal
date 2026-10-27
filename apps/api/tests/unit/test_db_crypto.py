"""Field encryption: the cipher, the key provider, the column type, and what hits the disk."""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr
from sqlalchemy import Column, MetaData, Table, text
from sqlalchemy.exc import StatementError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql.elements import ColumnElement

from unseal.config import DatabaseSettings
from unseal.db import crypto
from unseal.db.crypto import (
    DecryptionFailed,
    EncryptedText,
    InvalidEncryptionKey,
    MissingEncryptionKey,
    build_cipher,
    current_cipher,
    set_key_provider,
    settings_key_provider,
)
from unseal.db.models import Applicant, Base, User
from unseal.db.session import build_engine, build_session_factory

KEY_OLD = Fernet.generate_key().decode()
KEY_NEW = Fernet.generate_key().decode()

NAME = "Test Applicant"
ADDRESS = "Flat 0, Sample Nagar, Testville"
PHONE = "+910000000000"
CHAT_ID = "100000001"


@pytest.fixture(autouse=True)
def encryption_key() -> Iterator[None]:
    set_key_provider(lambda: KEY_OLD)
    yield
    set_key_provider(None)


# --- the cipher ---------------------------------------------------------------------------


def test_build_cipher_rejects_an_empty_key_list() -> None:
    for raw in ("", "   ", " , ,"):
        with pytest.raises(MissingEncryptionKey):
            build_cipher(raw)


def test_build_cipher_rejects_a_malformed_key_without_echoing_it() -> None:
    with pytest.raises(InvalidEncryptionKey) as caught:
        build_cipher("this-is-not-a-fernet-key")
    assert "this-is-not-a-fernet-key" not in str(caught.value)


def test_build_cipher_reports_which_entry_is_bad() -> None:
    with pytest.raises(InvalidEncryptionKey, match="entry 2"):
        build_cipher(f"{KEY_NEW}, bad-key")


def test_build_cipher_encrypts_with_the_first_key_and_decrypts_with_any() -> None:
    cipher = build_cipher(f" {KEY_NEW} , {KEY_OLD} ")
    token = cipher.encrypt(b"hello")
    assert Fernet(KEY_NEW.encode()).decrypt(token) == b"hello"
    with pytest.raises(InvalidToken):
        Fernet(KEY_OLD.encode()).decrypt(token)
    assert cipher.decrypt(Fernet(KEY_OLD.encode()).encrypt(b"older")) == b"older"


# --- the key provider ---------------------------------------------------------------------


def test_missing_key_fails_clearly_and_never_falls_back_to_plaintext() -> None:
    set_key_provider(lambda: None)
    with pytest.raises(MissingEncryptionKey, match="FIELD_ENCRYPTION_KEY"):
        current_cipher()
    with pytest.raises(MissingEncryptionKey):
        EncryptedText().process_bind_param(NAME, None)  # type: ignore[arg-type]


def test_blank_key_from_the_provider_counts_as_missing() -> None:
    set_key_provider(lambda: SecretStr(""))
    with pytest.raises(MissingEncryptionKey):
        current_cipher()


def test_provider_may_return_a_secretstr() -> None:
    set_key_provider(lambda: SecretStr(KEY_OLD))
    token = current_cipher().encrypt(b"x")
    assert Fernet(KEY_OLD.encode()).decrypt(token) == b"x"


def test_default_provider_reads_the_settings_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", KEY_NEW)
    crypto._database_settings.cache_clear()
    set_key_provider(None)
    try:
        key = settings_key_provider()
        assert key is not None
        assert key.get_secret_value() == KEY_NEW
        token = current_cipher().encrypt(b"x")
        assert Fernet(KEY_NEW.encode()).decrypt(token) == b"x"
    finally:
        crypto._database_settings.cache_clear()


def test_default_provider_without_a_key_in_settings_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FIELD_ENCRYPTION_KEY", raising=False)
    crypto._database_settings.cache_clear()
    monkeypatch.setattr(
        crypto,
        "_database_settings",
        lambda: DatabaseSettings(_env_file=None, field_encryption_key=None),
    )
    set_key_provider(None)
    with pytest.raises(MissingEncryptionKey):
        current_cipher()


# --- the column type, without a database --------------------------------------------------


def test_encrypted_text_binds_ciphertext_not_plaintext() -> None:
    bound = EncryptedText().process_bind_param(NAME, None)  # type: ignore[arg-type]
    assert bound is not None
    assert NAME not in bound
    assert Fernet(KEY_OLD.encode()).decrypt(bound.encode()).decode() == NAME


def test_encrypted_text_is_not_deterministic() -> None:
    column_type = EncryptedText()
    first = column_type.process_bind_param(NAME, None)  # type: ignore[arg-type]
    second = column_type.process_bind_param(NAME, None)  # type: ignore[arg-type]
    assert first != second


def test_encrypted_text_passes_none_through() -> None:
    column_type = EncryptedText()
    assert column_type.process_bind_param(None, None) is None  # type: ignore[arg-type]
    assert column_type.process_result_value(None, None) is None  # type: ignore[arg-type]


def test_encrypted_text_only_accepts_str() -> None:
    with pytest.raises(TypeError, match="str"):
        EncryptedText().process_bind_param(12345, None)  # type: ignore[arg-type]


def test_encrypted_text_result_decrypts() -> None:
    token = Fernet(KEY_OLD.encode()).encrypt(NAME.encode()).decode()
    assert EncryptedText().process_result_value(token, None) == NAME  # type: ignore[arg-type]


def test_undecryptable_value_raises_and_is_never_returned_as_plaintext() -> None:
    with pytest.raises(DecryptionFailed) as caught:
        EncryptedText().process_result_value(NAME, None)  # type: ignore[arg-type]
    assert NAME not in str(caught.value)


def test_value_encrypted_with_an_unknown_key_raises() -> None:
    foreign = Fernet(Fernet.generate_key()).encrypt(NAME.encode()).decode()
    with pytest.raises(DecryptionFailed):
        EncryptedText().process_result_value(foreign, None)  # type: ignore[arg-type]


_demo = Table("demo", MetaData(), Column("secret", EncryptedText()))


@pytest.mark.parametrize(
    "build",
    [
        lambda c: c == "x",
        lambda c: c != "x",
        lambda c: c.in_(["x"]),
        lambda c: c.like("x%"),
        lambda c: c.asc(),
        lambda c: "x" + c,
    ],
    ids=["eq", "ne", "in", "like", "asc", "reverse_add"],
)
def test_comparing_an_encrypted_column_fails_loudly(
    build: "object",
) -> None:
    # Tokens are random, so a WHERE on ciphertext would silently match nothing.
    with pytest.raises(TypeError, match="encrypted"):
        build(_demo.c.secret)  # type: ignore[operator]


def test_null_checks_on_an_encrypted_column_are_allowed() -> None:
    clause: ColumnElement[bool] = _demo.c.secret.is_(None)
    assert "IS NULL" in str(clause)
    assert "IS NOT NULL" in str(_demo.c.secret.is_not(None))


def test_comparing_an_orm_encrypted_attribute_fails_loudly() -> None:
    with pytest.raises(TypeError, match="encrypted"):
        _ = Applicant.name == NAME
    with pytest.raises(TypeError, match="encrypted"):
        _ = User.telegram_chat_id == CHAT_ID


# --- against a real database file ---------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "crypto.db"


@pytest.fixture
async def engine(db_path: Path) -> AsyncIterator[AsyncEngine]:
    eng = build_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return build_session_factory(engine)


async def add_applicant(
    factory: async_sessionmaker[AsyncSession],
    *,
    name: str = NAME,
    address: str | None = ADDRESS,
    phone: str | None = PHONE,
    chat_id: str | None = CHAT_ID,
) -> tuple[str, str]:
    async with factory() as session:
        user = User(channel="telegram", telegram_chat_id=chat_id, language="en")
        applicant = Applicant(user=user, name=name, address=address, phone=phone)
        session.add(user)
        await session.commit()
        return user.id, applicant.id


pytestmark = pytest.mark.anyio


async def test_applicant_fields_round_trip(factory: async_sessionmaker[AsyncSession]) -> None:
    user_id, applicant_id = await add_applicant(factory)
    async with factory() as session:
        applicant = await session.get(Applicant, applicant_id)
        user = await session.get(User, user_id)
        assert applicant is not None
        assert user is not None
        assert (applicant.name, applicant.address, applicant.phone) == (NAME, ADDRESS, PHONE)
        assert user.telegram_chat_id == CHAT_ID


async def test_stored_values_are_ciphertext(factory: async_sessionmaker[AsyncSession]) -> None:
    user_id, _ = await add_applicant(factory)
    async with factory() as session:
        # Plain SQL: bypasses the TypeDecorator, so this is what is actually stored.
        applicant_row = (
            await session.execute(text("SELECT name, address, phone FROM applicants"))
        ).one()
        chat_row = (
            await session.execute(
                text("SELECT telegram_chat_id FROM users WHERE id = :id"), {"id": user_id}
            )
        ).one()
    for plaintext, stored in zip((NAME, ADDRESS, PHONE), applicant_row, strict=True):
        assert plaintext not in stored
        assert Fernet(KEY_OLD.encode()).decrypt(stored.encode()).decode() == plaintext
    assert CHAT_ID not in chat_row[0]
    assert Fernet(KEY_OLD.encode()).decrypt(chat_row[0].encode()).decode() == CHAT_ID


async def test_plaintext_never_reaches_the_database_file(
    factory: async_sessionmaker[AsyncSession], engine: AsyncEngine, db_path: Path
) -> None:
    await add_applicant(factory)
    await engine.dispose()
    raw = db_path.read_bytes()
    for plaintext in (NAME, ADDRESS, PHONE, CHAT_ID):
        assert plaintext.encode() not in raw


async def test_null_and_empty_values(factory: async_sessionmaker[AsyncSession]) -> None:
    _, applicant_id = await add_applicant(factory, address="", phone=None, chat_id=None)
    async with factory() as session:
        applicant = await session.get(Applicant, applicant_id)
        assert applicant is not None
        assert applicant.address == ""
        assert applicant.phone is None
        row = (await session.execute(text("SELECT address, phone FROM applicants"))).one()
    assert row[0] != ""  # an empty string is still encrypted
    assert row[1] is None  # NULL stays NULL


async def test_writing_without_a_key_fails_and_leaks_nothing(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    set_key_provider(lambda: None)
    with pytest.raises(StatementError) as caught:
        await add_applicant(factory)
    assert isinstance(caught.value.orig, MissingEncryptionKey)
    # The error text is what ends up in logs: it must not carry the plaintext parameters.
    assert NAME not in str(caught.value)
    assert ADDRESS not in str(caught.value)
    set_key_provider(lambda: KEY_OLD)
    async with factory() as session:
        count = (await session.execute(text("SELECT count(*) FROM applicants"))).scalar_one()
    assert count == 0


async def test_reading_without_a_key_fails(factory: async_sessionmaker[AsyncSession]) -> None:
    _, applicant_id = await add_applicant(factory)
    set_key_provider(lambda: None)
    async with factory() as session:
        with pytest.raises(MissingEncryptionKey):
            await session.get(Applicant, applicant_id)


async def test_reading_with_the_wrong_key_fails(factory: async_sessionmaker[AsyncSession]) -> None:
    _, applicant_id = await add_applicant(factory)
    set_key_provider(lambda: Fernet.generate_key().decode())
    async with factory() as session:
        with pytest.raises(DecryptionFailed):
            await session.get(Applicant, applicant_id)


async def test_plaintext_planted_in_an_encrypted_column_is_refused(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    _, applicant_id = await add_applicant(factory)
    async with factory() as session:
        await session.execute(
            text("UPDATE applicants SET name = :n WHERE id = :id"),
            {"n": NAME, "id": applicant_id},
        )
        await session.commit()
    async with factory() as session:
        with pytest.raises(DecryptionFailed):
            await session.get(Applicant, applicant_id)


async def test_key_rotation_reads_old_data_and_writes_with_the_new_key(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    _, applicant_id = await add_applicant(factory)
    new_only = Fernet(KEY_NEW.encode())
    old_only = Fernet(KEY_OLD.encode())

    # Rotation: new key first, old key kept for reading.
    set_key_provider(lambda: f"{KEY_NEW},{KEY_OLD}")
    async with factory() as session:
        applicant = await session.get(Applicant, applicant_id)
        assert applicant is not None
        assert applicant.name == NAME  # decrypted with the old key
        applicant.name = "Test Applicant Renamed"  # a changed value is written with the new key
        flag_modified(applicant, "address")  # force-rewrite an unchanged one, as a rotation job
        await session.commit()

    async with factory() as session:
        row = (await session.execute(text("SELECT name, address, phone FROM applicants"))).one()
    assert new_only.decrypt(row[0].encode()).decode() == "Test Applicant Renamed"
    assert new_only.decrypt(row[1].encode()).decode() == ADDRESS
    for token in row[:2]:
        with pytest.raises(InvalidToken):
            old_only.decrypt(token.encode())  # no longer readable with the old key alone
    # An untouched field is still under the old key until something rewrites it.
    assert old_only.decrypt(row[2].encode()).decode() == PHONE

    # Retiring the old key too early breaks rows that were not rewritten ...
    set_key_provider(lambda: KEY_NEW)
    async with factory() as session:
        with pytest.raises(DecryptionFailed):
            await session.get(Applicant, applicant_id)

    # ... and once every field has been rewritten, the old key is no longer needed.
    set_key_provider(lambda: f"{KEY_NEW},{KEY_OLD}")
    async with factory() as session:
        applicant = await session.get(Applicant, applicant_id)
        assert applicant is not None
        flag_modified(applicant, "phone")
        await session.commit()
    set_key_provider(lambda: KEY_NEW)
    async with factory() as session:
        applicant = await session.get(Applicant, applicant_id)
        assert applicant is not None
        assert (applicant.name, applicant.address, applicant.phone) == (
            "Test Applicant Renamed",
            ADDRESS,
            PHONE,
        )
