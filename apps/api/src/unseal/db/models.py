"""SQLAlchemy 2 models: users, applicants, cases, questions, deadlines, documents (PRD data model).

Conventions:
- IDs are UUIDv4 strings (36 chars), opaque in URLs. Timestamps are UTC (`UTCDateTime`); days are
  plain `DATE`s computed in Asia/Kolkata by the rules engine, never here.
- Personal data (applicant name, address, phone, Telegram chat id) uses `EncryptedText`.
- Deleting a user, an applicant or a case removes everything beneath it: ORM cascades plus
  `ON DELETE CASCADE` foreign keys (SQLite needs the pragma that `session.build_engine` sets).
  Stored files are deleted by the service layer, not here.
- Allowed values are CHECK constraints built from the enums below, so the database refuses a bad
  status even if application code does not. Adding a value needs an Alembic migration.
- Relationships are lazy by default; in async code load them with `selectinload` (or similar).
"""

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from unseal.db.crypto import EncryptedText

# Explicit constraint names keep migrations reviewable and let SQLite batch operations work.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Channel(StrEnum):
    WEB = "web"
    TELEGRAM = "telegram"


class Language(StrEnum):
    EN = "en"
    HI = "hi"
    TA = "ta"


class CaseStatus(StrEnum):
    """FR-7 order. A transfer is an event (see `Case.transferred_to`), not a status."""

    DRAFT = "draft"
    FILED = "filed"
    REPLY_DUE = "reply_due"
    REPLIED = "replied"
    DEEMED_REFUSED = "deemed_refused"
    APPEALED = "appealed"
    CLOSED = "closed"


class DeadlineKind(StrEnum):
    PIO_REPLY = "pio_reply"
    FIRST_APPEAL = "first_appeal"
    FAA_DECISION = "faa_decision"
    SECOND_APPEAL = "second_appeal"


class DocumentKind(StrEnum):
    APPLICATION = "application"
    FIRST_APPEAL = "first_appeal"
    SECOND_APPEAL = "second_appeal"
    REPLY_IMAGE = "reply_image"


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


def _one_of(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(member.value) for member in values)})"


class UTCDateTime(TypeDecorator[datetime]):
    """A timezone-aware UTC timestamp. Naive datetimes are refused (they are always a bug), and
    values read back from SQLite, which drops the zone, are marked UTC again."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware; pass UTC (datetime.now(UTC))")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


UuidPk = Annotated[str, mapped_column(String(36), primary_key=True, default=new_id)]


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(_one_of("channel", Channel), name="channel"),
        CheckConstraint(_one_of("language", Language), name="language"),
    )

    id: Mapped[UuidPk]
    channel: Mapped[str] = mapped_column(String(16))
    telegram_chat_id: Mapped[str | None] = mapped_column(EncryptedText())
    language: Mapped[str] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    # ADR 0003: SHA-256 of the web session token, and HMAC of the Telegram chat id (lookup keys;
    # the token itself is never stored, the chat id is stored encrypted above).
    session_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    telegram_chat_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)

    applicants: Mapped[list["Applicant"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    cases: Mapped[list["Case"]] = relationship(
        back_populates="user", cascade="all", passive_deletes=True
    )


class Applicant(Base):
    __tablename__ = "applicants"

    id: Mapped[UuidPk]
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(EncryptedText())
    # Nullable: the validator blocks export while the address is missing, so a draft may lack it.
    address: Mapped[str | None] = mapped_column(EncryptedText())
    phone: Mapped[str | None] = mapped_column(EncryptedText())
    # Below poverty line (S. 7(5)): no fee; the application states it and attaches proof.
    bpl: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    user: Mapped[User] = relationship(back_populates="applicants")
    cases: Mapped[list["Case"]] = relationship(
        back_populates="applicant", cascade="all", passive_deletes=True
    )


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint(_one_of("status", CaseStatus), name="status"),
        CheckConstraint(_one_of("language", Language), name="language"),
        # The 180-day retention job selects closed cases by age.
        Index("ix_cases_status_closed_on", "status", "closed_on"),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Nullable: a case starts as a draft before the applicant's details are entered.
    applicant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("applicants.id", ondelete="CASCADE"), index=True
    )
    # "central" or "tamil_nadu" today; validated against the rules data, not constrained here,
    # so adding a state does not need a migration.
    jurisdiction: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(2))
    # Nullable while drafting; the validator blocks export until they are filled.
    authority_name: Mapped[str | None] = mapped_column(Text)
    pio_address: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=CaseStatus.DRAFT.value)
    via_apio: Mapped[bool] = mapped_column(Boolean, default=False)
    third_party: Mapped[bool] = mapped_column(Boolean, default=False)
    life_liberty: Mapped[bool] = mapped_column(Boolean, default=False)
    filing_mode: Mapped[str | None] = mapped_column(String(32))
    filed_on: Mapped[date | None] = mapped_column(Date)
    received_on: Mapped[date | None] = mapped_column(Date)
    # True while received_on is the engine's estimate (filed_on plus the transit buffer).
    received_estimated: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # The day the PIO's reply arrived: the S. 19(1) window runs from it, and the appeal cites it.
    reply_received_on: Mapped[date | None] = mapped_column(Date)
    # The day the first appeal was filed: the FAA's S. 19(6) clock runs from it.
    appeal_filed_on: Mapped[date | None] = mapped_column(Date)
    # The day the appellate authority's order arrived: the S. 19(3) window runs from it.
    faa_decision_received_on: Mapped[date | None] = mapped_column(Date)
    # Set when the case is closed; the retention job deletes 180 days later.
    closed_on: Mapped[date | None] = mapped_column(Date)
    # A transfer (S. 6(3)) is an event: the new authority and when it received the application.
    transferred_to: Mapped[str | None] = mapped_column(Text)
    transfer_received_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    user: Mapped[User] = relationship(back_populates="cases")
    applicant: Mapped[Applicant | None] = relationship(back_populates="cases")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Question.position",
    )
    deadlines: Mapped[list["Deadline"]] = relationship(
        back_populates="case", cascade="all, delete-orphan", passive_deletes=True
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="case", cascade="all, delete-orphan", passive_deletes=True
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[UuidPk]
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    # Order of the numbered questions in the application.
    position: Mapped[int] = mapped_column(Integer)
    # Encrypted: questions carry register numbers and grievance details.
    original_text: Mapped[str] = mapped_column(EncryptedText())
    rewritten_text: Mapped[str | None] = mapped_column(EncryptedText())
    # JSON of the rewrite step's records_requested, reason and suggestion (encrypted: they repeat
    # the grievance). personal_information is the step's flag, kept plain for the validator.
    details: Mapped[str | None] = mapped_column(EncryptedText())
    personal_information: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    # Validator flag codes (for example "personal_information"), not free text from the user.
    flags: Mapped[list[Any]] = mapped_column(JSON, default=list)

    case: Mapped[Case] = relationship(back_populates="questions")


class Deadline(Base):
    __tablename__ = "deadlines"
    __table_args__ = (
        CheckConstraint(_one_of("kind", DeadlineKind), name="kind"),
        UniqueConstraint("case_id", "kind"),
        Index("ix_deadlines_due_on", "due_on"),
    )

    id: Mapped[UuidPk]
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    due_on: Mapped[date] = mapped_column(Date)
    # The 48-hour (life or liberty) track uses a UTC timestamp instead of a day.
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    # FR-9: three reminders per deadline, each sent exactly once. A marker is claimed with a
    # conditional update before sending, so concurrent scheduler runs cannot double-send.
    reminded_7d_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reminded_1d_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reminded_due_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    case: Mapped[Case] = relationship(back_populates="deadlines")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (CheckConstraint(_one_of("kind", DocumentKind), name="kind"),)

    id: Mapped[UuidPk]
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16))
    # Opaque key into file storage; never a file name built from personal data.
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    case: Mapped[Case] = relationship(back_populates="documents")
