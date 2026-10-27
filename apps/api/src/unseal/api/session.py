"""Session and account routes (docs/api.md "Session and account", FR-8)."""

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from unseal.api.deps import SESSION_COOKIE, Config, CurrentUser, Db, LanguageCode
from unseal.db.models import Case, Document
from unseal.services.cases import export_cases
from unseal.services.identity import create_web_user, user_for_token
from unseal.services.storage import remove_files

router = APIRouter()

SESSION_MAX_AGE = 60 * 60 * 24 * 365  # the cookie is the only key to an anonymous account


class LanguageBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: LanguageCode


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/session", status_code=204)
async def start_session(
    body: LanguageBody, request: Request, session: Db, config: Config
) -> Response:
    response = Response(status_code=204)
    if await user_for_token(session, request.cookies.get(SESSION_COOKIE, "")) is not None:
        return response  # idempotent: a valid cookie keeps its user
    _, token = await create_web_user(session, language=body.language)
    await session.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=True,
        samesite=config.session_cookie_samesite,
        path="/",
    )
    return response


@router.get("/me")
async def me(user: CurrentUser, session: Db) -> dict[str, object]:
    count = select(func.count()).select_from(Case).where(Case.user_id == user.id)
    return {"language": user.language, "cases": (await session.execute(count)).scalar_one()}


@router.patch("/me", status_code=204)
async def update_me(body: LanguageBody, user: CurrentUser, session: Db) -> Response:
    user.language = body.language
    await session.commit()
    return Response(status_code=204)


@router.delete("/me", status_code=204)
async def delete_me(user: CurrentUser, session: Db, config: Config) -> Response:
    """FR-8: every row (by cascade) and every stored file of this user."""
    keys = select(Document.storage_key).join(Case).where(Case.user_id == user.id)
    storage_keys = list((await session.execute(keys)).scalars())
    await session.delete(user)
    await session.commit()
    remove_files(config.storage_dir, storage_keys)
    response = Response(status_code=204)
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=True,
        httponly=True,
        samesite=config.session_cookie_samesite,
    )
    return response


@router.get("/me/export")
async def export_me(user: CurrentUser, session: Db) -> JSONResponse:
    body = {"language": user.language, "cases": await export_cases(session, user)}
    headers = {"Content-Disposition": 'attachment; filename="unseal-export.json"'}
    return JSONResponse(body, headers=headers)
