"""What the bot handlers are given: the same service objects the API routes use, plus a per-chat
quota on model calls."""

import hashlib
from dataclasses import dataclass

from limits import RateLimitItem, parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from unseal.config import Settings
from unseal.harness.steps import StructuredLLM
from unseal.services.cases import Renderer


@dataclass(frozen=True)
class BotServices:
    """Injected so tests use fakes (same objects as the FastAPI app state)."""

    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    llm: StructuredLLM
    renderer: Renderer


class ChatQuota:
    """Model calls per chat (pentest item 7: Telegram traffic is metered per chat, because every
    webhook request comes from Telegram's few IPs). Keys are hashed chat ids.
    ponytail: in-memory, so per process; move to Redis with the API's limiter if it scales out."""

    def __init__(self, limit: str) -> None:
        self._limiter = MovingWindowRateLimiter(MemoryStorage())
        self._item: RateLimitItem = parse(limit)

    def allow(self, chat_id: int) -> bool:
        key = hashlib.sha256(str(chat_id).encode()).hexdigest()
        return self._limiter.hit(self._item, "telegram", key)
