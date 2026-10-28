"""Database layer: SQLAlchemy 2 models, async sessions, and Fernet field encryption."""

from unseal.db.crypto import (
    DecryptionFailed,
    EncryptedText,
    EncryptionKeyError,
    InvalidEncryptionKey,
    MissingEncryptionKey,
    set_key_provider,
)
from unseal.db.models import (
    Applicant,
    Base,
    Case,
    CaseStatus,
    Channel,
    Deadline,
    DeadlineKind,
    Document,
    DocumentKind,
    Language,
    Question,
    User,
)
from unseal.db.session import (
    build_engine,
    build_session_factory,
    dispose_engine,
    get_engine,
    get_session,
    get_session_factory,
)

__all__ = [
    "Applicant",
    "Base",
    "Case",
    "CaseStatus",
    "Channel",
    "Deadline",
    "DeadlineKind",
    "DecryptionFailed",
    "Document",
    "DocumentKind",
    "EncryptedText",
    "EncryptionKeyError",
    "InvalidEncryptionKey",
    "Language",
    "MissingEncryptionKey",
    "Question",
    "User",
    "build_engine",
    "build_session_factory",
    "dispose_engine",
    "get_engine",
    "get_session",
    "get_session_factory",
    "set_key_provider",
]
