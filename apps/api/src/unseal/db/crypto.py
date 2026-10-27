"""Field-level encryption for personal data (Fernet, with MultiFernet for key rotation).

`EncryptedText` is a SQLAlchemy column type: values are encrypted on the way into the database and
decrypted on the way out, so plaintext never reaches a table, a backup or a SQL log. It is
applied to `applicants.name`, `applicants.address`, `applicants.phone` and
`users.telegram_chat_id`.

Keys: FIELD_ENCRYPTION_KEY holds one Fernet key, or several separated by commas. The first key
encrypts; every key can decrypt. To rotate, put the new key first and keep the old one until every
row has been rewritten, then drop it. A missing or malformed key raises on first use; there is never
a fallback to storing plaintext.

Limits that follow from the design:
- Tokens carry a random nonce, so the same value encrypts differently each time. An encrypted column
  cannot be filtered, joined or sorted; comparing it raises `TypeError` instead of silently matching
  nothing. Only `IS NULL` / `IS NOT NULL` are allowed. Looking a user up by Telegram chat id needs a
  separate blind index; that does not exist yet.
- Do not log or print a decrypted value.
"""

from collections.abc import Callable
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from pydantic import SecretStr
from sqlalchemy import Text
from sqlalchemy.engine import Dialect
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.operators import OperatorType
from sqlalchemy.types import TypeDecorator

from unseal.config import DatabaseSettings

KeyProvider = Callable[[], str | SecretStr | None]

_ALLOWED_OPERATORS = (operators.is_, operators.is_not)
_NOT_COMPARABLE = (
    "This column is encrypted with a random nonce, so it cannot be compared, filtered "
    "or sorted in SQL. Only IS NULL / IS NOT NULL checks are allowed."
)


class EncryptionKeyError(RuntimeError):
    """Base class for key and decryption problems. Messages never contain keys or values."""


class MissingEncryptionKey(EncryptionKeyError):
    """FIELD_ENCRYPTION_KEY is not set (or is blank)."""


class InvalidEncryptionKey(EncryptionKeyError):
    """A configured key is not a valid Fernet key."""


class DecryptionFailed(EncryptionKeyError):
    """A stored value could not be decrypted with any configured key."""


@lru_cache(maxsize=1)
def _database_settings() -> DatabaseSettings:
    return DatabaseSettings()


def settings_key_provider() -> SecretStr | None:
    """The default key source: FIELD_ENCRYPTION_KEY from the environment."""
    return _database_settings().field_encryption_key


_provider: KeyProvider = settings_key_provider


def set_key_provider(provider: KeyProvider | None) -> None:
    """Swap where keys come from (tests, key-management hooks). None restores the default."""
    global _provider
    _provider = provider if provider is not None else settings_key_provider


def build_cipher(raw_keys: str) -> MultiFernet:
    """Parse a comma-separated list of Fernet keys. The first encrypts; all of them decrypt."""
    keys = [key.strip() for key in raw_keys.split(",") if key.strip()]
    if not keys:
        raise MissingEncryptionKey(_missing_message())
    fernets: list[Fernet] = []
    for position, key in enumerate(keys, start=1):
        try:
            fernets.append(Fernet(key))
        except ValueError:
            raise InvalidEncryptionKey(
                f"FIELD_ENCRYPTION_KEY entry {position} is not a valid Fernet key "
                "(expected 32 url-safe base64-encoded bytes)"
            ) from None
    return MultiFernet(fernets)


def current_cipher() -> MultiFernet:
    """The cipher for the configured keys. Raises MissingEncryptionKey if there are none."""
    raw = _provider()
    if raw is None:
        raise MissingEncryptionKey(_missing_message())
    if isinstance(raw, SecretStr):
        raw = raw.get_secret_value()
    return build_cipher(raw)


def _missing_message() -> str:
    return (
        "FIELD_ENCRYPTION_KEY is not set. Generate a key with "
        '`python -c "from cryptography.fernet import Fernet; '
        'print(Fernet.generate_key().decode())"` and set it in the server environment.'
    )


class EncryptedText(TypeDecorator[str]):
    """A text column stored as a Fernet token. See the module docstring for the limits."""

    impl = Text
    cache_ok = True

    class comparator_factory(TypeDecorator.Comparator[str]):  # noqa: N801
        def operate(self, op: OperatorType, *other: Any, **kwargs: Any) -> ColumnElement[Any]:
            if op not in _ALLOWED_OPERATORS:
                raise TypeError(_NOT_COMPARABLE)
            return super().operate(op, *other, **kwargs)

        def reverse_operate(
            self, op: OperatorType, other: Any, **kwargs: Any
        ) -> ColumnElement[Any]:
            raise TypeError(_NOT_COMPARABLE)

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError(f"EncryptedText stores str values, got {type(value).__name__}")
        return current_cipher().encrypt(value.encode("utf-8")).decode("ascii")

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        try:
            return current_cipher().decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            raise DecryptionFailed(
                "A stored value could not be decrypted: the key is wrong, an old key was "
                "retired too early, or the column holds data that was never encrypted."
            ) from None
