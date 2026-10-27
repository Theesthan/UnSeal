"""Request dependencies: a database session per request and the signed-in anonymous user."""

from collections.abc import AsyncIterator
from typing import Annotated, Literal

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from unseal.api.errors import ApiError
from unseal.config import Settings
from unseal.db.models import User
from unseal.services.identity import user_for_token

SESSION_COOKIE = "unseal_session"

LanguageCode = Literal["en", "hi", "ta"]


async def db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


def settings(request: Request) -> Settings:
    config: Settings = request.app.state.settings
    return config


Db = Annotated[AsyncSession, Depends(db)]
Config = Annotated[Settings, Depends(settings)]


async def current_user(request: Request, session: Db) -> User:
    user = await user_for_token(session, request.cookies.get(SESSION_COOKIE, ""))
    if user is None:
        raise ApiError(401, "no_session")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
