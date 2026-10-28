"""Shared fakes for the Telegram bot tests (imported by test_bot_*.py and test_api_telegram.py).

A recording Bot API request object (a real `telegram.request.BaseRequest` subclass, so the real
python-telegram-bot `Application` runs offline), a fake model, a fake PDF renderer, and a driver
that plays one fictional chat. Fictional data only.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from pydantic import BaseModel, SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telegram import Update
from telegram.request import BaseRequest, RequestData

from unseal.bot.app import BotServices, build_application
from unseal.config import Settings
from unseal.db.crypto import set_key_provider
from unseal.db.models import Applicant, Base, Case, Deadline, Document, Question, User
from unseal.db.session import build_engine, build_session_factory
from unseal.llm.client import StructuredResult
from unseal.pdf.models import ApplicationDocument
from unseal.scheduler import Reminder
from unseal.services import cases as case_service
from unseal.services.identity import create_web_user, telegram_user
from unseal.services.intake import IntakeResult

CHAT_ID = 5550001  # fictional
BOT_TOKEN = "123456:TEST-token-for-unit-tests-only"
WEBHOOK_SECRET = "test-webhook-secret"
CHAT_KEY = "test-chat-hash-key"
NAME, ADDRESS = "Test Applicant", "12 Sample Street, Chennai"
BOT_USER = {"id": 1, "is_bot": True, "first_name": "UnSeal", "username": "unseal_test_bot"}
_MESSAGE_ENDPOINTS = ("sendMessage", "sendDocument", "editMessageText", "editMessageReplyMarkup")
_TEXT_ENDPOINTS = ("sendMessage", "editMessageText")


def use_test_key() -> Iterator[None]:
    """For an autouse fixture: a fresh Fernet test key for the duration of one test."""
    key = Fernet.generate_key().decode()
    set_key_provider(lambda: key)
    yield
    set_key_provider(None)


@dataclass(frozen=True)
class Call:
    endpoint: str
    params: dict[str, Any]


class FakeRequest(BaseRequest):
    """Records every Bot API call and answers with canned JSON; uploaded files are kept."""

    def __init__(self, *, fail_get_me: bool = False) -> None:
        self.calls: list[Call] = []
        self.documents: list[bytes] = []
        self._fail_get_me = fail_get_me
        self._next_id = 1000

    async def initialize(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None

    @property
    def read_timeout(self) -> float | None:
        return 1.0

    async def do_request(
        self,
        url: str,
        method: str,
        request_data: RequestData | None = None,
        read_timeout: Any = None,
        write_timeout: Any = None,
        connect_timeout: Any = None,
        pool_timeout: Any = None,
    ) -> tuple[int, bytes]:
        endpoint = url.rsplit("/", 1)[-1]
        params: dict[str, Any] = dict(request_data.parameters) if request_data else {}
        if request_data:
            for _, content, _ in request_data.multipart_data.values():
                assert isinstance(content, bytes)
                self.documents.append(content)
        self.calls.append(Call(endpoint, params))
        if endpoint == "getMe" and self._fail_get_me:
            body = {"ok": False, "error_code": 401, "description": "Unauthorized"}
            return 401, json.dumps(body).encode()
        return 200, json.dumps({"ok": True, "result": self._result(endpoint, params)}).encode()

    def _result(self, endpoint: str, params: dict[str, Any]) -> object:
        if endpoint == "getMe":
            return BOT_USER
        if endpoint in _MESSAGE_ENDPOINTS:
            self._next_id += 1
            chat = {"id": params.get("chat_id", CHAT_ID), "type": "private"}
            return {"message_id": self._next_id, "date": 0, "chat": chat, "text": "ok"}
        return True

    # ---- reading what the bot did

    def sent(self, *endpoints: str) -> list[Call]:
        return [call for call in self.calls if call.endpoint in endpoints]

    def texts(self) -> list[str]:
        return [str(call.params["text"]) for call in self.sent(*_TEXT_ENDPOINTS)]

    def last_text(self) -> str:
        return self.texts()[-1]

    def answers(self) -> list[str]:
        return [str(c.params.get("text", "")) for c in self.sent("answerCallbackQuery")]

    def buttons(self) -> list[tuple[str, str]]:
        """(label, callback_data) of the keyboard on the most recent call that carried one."""
        for call in reversed(self.calls):
            markup = call.params.get("reply_markup")
            if markup and "inline_keyboard" in markup:
                rows = markup["inline_keyboard"]
                return [(b["text"], b["callback_data"]) for row in rows for b in row]
        return []

    def everything_said(self) -> str:
        """Every text, caption and button label the bot sent: for privacy assertions."""
        parts = [str(c.params.get(k, "")) for c in self.calls for k in ("text", "caption")]
        return "\n".join(parts + [label for label, _ in self.buttons()])


class FakeLLM:
    """Answers structured calls in order; an Exception in the queue is raised instead."""

    def __init__(self, *results: BaseModel | Exception) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def structured_call(self, output: type[Any], **kwargs: Any) -> StructuredResult[Any]:
        self.calls.append({"output": output, **kwargs})
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        return StructuredResult(item, "req-1", 0, False)


class FakeRenderer:
    def __init__(self) -> None:
        self.documents: list[ApplicationDocument] = []

    def __call__(self, doc: ApplicationDocument) -> bytes:
        self.documents.append(doc)
        return b"%PDF-1.7 fake application " + str(len(self.documents)).encode()


def bot_settings(tmp_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "bharatcode_api_key": "test-key",
        "database_url": f"sqlite+aiosqlite:///{(tmp_path / 'bot.db').as_posix()}",
        "storage_dir": tmp_path / "storage",
        "telegram_bot_token": BOT_TOKEN,
        "telegram_webhook_secret": WEBHOOK_SECRET,
        "telegram_chat_hash_key": CHAT_KEY,
        **overrides,
    }
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


async def make_db(settings: Settings) -> async_sessionmaker[AsyncSession]:
    engine = build_engine(settings.database_url.get_secret_value())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return build_session_factory(engine)


async def row_counts(factory: async_sessionmaker[AsyncSession]) -> dict[str, int]:
    counts = {}
    async with factory() as session:
        for model in (User, Applicant, Case, Question, Deadline, Document):
            query = select(func.count()).select_from(model)
            counts[model.__tablename__] = (await session.execute(query)).scalar_one()
    return counts


def intake_result(
    *,
    follow_ups: list[str] | None = None,
    hint: str = "tamil_nadu",
    authorities: list[dict[str, Any]] | None = None,
) -> IntakeResult:
    return IntakeResult.model_validate(
        {
            "intake": {
                "jurisdiction_hint": hint,
                "authority": None,
                "time_period": None,
                "records_wanted": ["answer script"],
                "delivery_mode": "unknown",
                "bpl": "unknown",
                "follow_up_questions": follow_ups or [],
                "ready_to_draft": not follow_ups,
            },
            "authorities": authorities if authorities is not None else [UNIVERSITY, BOARD],
        }
    )


UNIVERSITY: dict[str, Any] = {
    "id": "sample-university",
    "name": "Sample State University, Examination Branch",
    "name_ta": "மாதிரி மாநிலப் பல்கலைக்கழகம், தேர்வுப் பிரிவு",
    "name_hi": None,
    "jurisdiction": "tamil_nadu",
    "pio_designation": "Public Information Officer",
    "pio_address": "Examination Branch, Sample State University, 1 College Road, Chennai 600000",
    "rti_online": False,
}
BOARD: dict[str, Any] = {
    "id": "sample-board",
    "name": "Sample Central Board, Regional Office",
    "name_ta": None,
    "name_hi": None,
    "jurisdiction": "central",
    "pio_designation": "CPIO",
    "pio_address": "Sample Central Board, Regional Office, 2 Board Street, Chennai 600001",
    "rti_online": True,
}


class ChatDriver:
    """One fictional private chat talking to a real PTB Application."""

    def __init__(self, application: Any, request: FakeRequest, chat_id: int = CHAT_ID) -> None:
        self.application = application
        self.request = request
        self.chat_id = chat_id
        self._update_id = 0

    def _next(self) -> int:
        self._update_id += 1
        return self._update_id

    def _user(self) -> dict[str, Any]:
        return {"id": self.chat_id, "is_bot": False, "first_name": "Test"}

    def _chat(self) -> dict[str, Any]:
        return {"id": self.chat_id, "type": "private"}

    def message_update(self, text: str) -> dict[str, Any]:
        number = self._next()
        message: dict[str, Any] = {
            "message_id": number,
            "date": 1_790_000_000,
            "chat": self._chat(),
            "from": self._user(),
            "text": text,
        }
        if text.startswith("/"):
            command = text.split()[0]
            message["entities"] = [{"type": "bot_command", "offset": 0, "length": len(command)}]
        return {"update_id": number, "message": message}

    def callback_update(self, data: str) -> dict[str, Any]:
        number = self._next()
        shown = {"message_id": 900, "date": 0, "chat": self._chat(), "from": BOT_USER, "text": "x"}
        query = {
            "id": f"cq-{number}",
            "from": self._user(),
            "chat_instance": "test-instance",
            "data": data,
            "message": shown,
        }
        return {"update_id": number, "callback_query": query}

    async def _process(self, payload: dict[str, Any]) -> None:
        await self.application.process_update(Update.de_json(payload, self.application.bot))

    async def send(self, text: str) -> None:
        await self._process(self.message_update(text))

    async def tap(self, data: str) -> None:
        await self._process(self.callback_update(data))

    def button(self, label: str) -> str:
        """The callback data of the button labelled `label` on the last keyboard shown."""
        offered = self.request.buttons()
        matches = [data for text, data in offered if text == label]
        assert matches, f"no button {label!r} in {offered!r}"
        return matches[0]

    async def press(self, label: str) -> None:
        await self.tap(self.button(label))


class FakeIntake:
    """Stands in for services.intake.run_intake (monkeypatched); records what it was given."""

    def __init__(self, *results: IntakeResult | Exception) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, llm: object, message: str, *, language: str) -> IntakeResult:
        self.calls.append((message, language))
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@dataclass
class Harness:
    application: Any
    request: FakeRequest
    llm: FakeLLM
    renderer: FakeRenderer
    factory: async_sessionmaker[AsyncSession]
    settings: Settings
    chat: ChatDriver

    async def counts(self) -> dict[str, int]:
        return await row_counts(self.factory)

    async def close(self) -> None:
        if self.application.running:
            await self.application.stop()
        await self.application.shutdown()
        await dispose(self.factory)


async def dispose(factory: async_sessionmaker[AsyncSession]) -> None:
    """Close the test engine's pooled connections before the test's event loop ends."""
    await factory.kw["bind"].dispose()


async def start_harness(
    tmp_path: Path, llm: FakeLLM | None = None, *, block: bool = True, **overrides: Any
) -> Harness:
    """A real, initialised PTB Application over a temp SQLite DB, the fakes and one chat."""
    settings = bot_settings(tmp_path, **overrides)
    factory = await make_db(settings)
    fake_llm, renderer, request = llm or FakeLLM(), FakeRenderer(), FakeRequest()
    services = BotServices(
        settings=settings, session_factory=factory, llm=fake_llm, renderer=renderer
    )
    application = build_application(
        services, request=request, get_updates_request=FakeRequest(), block=block
    )
    await application.initialize()
    chat = ChatDriver(application, request)
    return Harness(application, request, fake_llm, renderer, factory, settings, chat)


FILED = date(2026, 10, 27)


async def filed_case(
    factory: async_sessionmaker[AsyncSession], *, telegram: bool, language: str = "ta"
) -> Case:
    """A filed Tamil Nadu case with an applicant, for a Telegram or a web user."""
    async with factory() as session:
        if telegram:
            user = await telegram_user(session, CHAT_ID, key=SecretStr(CHAT_KEY), language=language)
        else:
            user, _ = await create_web_user(session, language=language)
        case = await case_service.create_case(
            session, user, language=language, jurisdiction="tamil_nadu"
        )
        authority = case_service.AuthorityInput(
            jurisdiction="tamil_nadu",
            authority_name="Sample State University",
            pio_address="1 College Road, Chennai",
        )
        await case_service.set_authority(session, case, authority)
        await case_service.set_applicant(
            session, case, case_service.ApplicantInput(name=NAME, address=ADDRESS)
        )
        await case_service.file_case(
            session, case, case_service.FilingInput(filed_on=FILED, filing_mode="post")
        )
        return await case_service.get_case(session, user, case.id)


def reminder_for(case: Case, kind: str, window: str) -> Reminder:
    deadline = next(d for d in case.deadlines if d.kind == kind)
    return Reminder(deadline.id, case.id, deadline.kind, deadline.due_on, window)


def test_fake_request_reads_the_last_keyboard() -> None:
    request = FakeRequest()
    request.calls.append(
        Call("sendMessage", {"text": "a", "reply_markup": {"inline_keyboard": []}})
    )
    markup = {"inline_keyboard": [[{"text": "Go", "callback_data": "go"}]]}
    request.calls.append(Call("editMessageText", {"text": "b", "reply_markup": markup}))
    request.calls.append(Call("answerCallbackQuery", {"text": "c"}))
    assert request.buttons() == [("Go", "go")]
    assert request.texts() == ["a", "b"] and request.answers() == ["c"]
