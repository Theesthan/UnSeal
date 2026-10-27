"""Case routes (docs/api.md "Cases"). Thin: parse, call services.cases, shape the response."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict

from unseal.api.deps import Config, CurrentUser, Db, LanguageCode
from unseal.api.ratelimit import ModelQuota
from unseal.db.models import Case
from unseal.rules.engine import Jurisdiction
from unseal.services import cases as svc

router = APIRouter(prefix="/cases")


class NewCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: LanguageCode
    jurisdiction: Jurisdiction = "central"


class QuestionText(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


class QuestionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rewritten_text: str | None = None
    accepted: bool | None = None


async def owned_case(case_id: str, user: CurrentUser, session: Db) -> Case:
    return await svc.get_case(session, user, case_id)


OwnedCase = Annotated[Case, Depends(owned_case)]


@router.post("", status_code=201)
async def create(body: NewCase, user: CurrentUser, session: Db) -> dict[str, Any]:
    case = await svc.create_case(
        session, user, language=body.language, jurisdiction=body.jurisdiction
    )
    return svc.case_view(case)


@router.get("")
async def list_all(user: CurrentUser, session: Db) -> list[dict[str, Any]]:
    return [svc.case_summary(case) for case in await svc.list_cases(session, user)]


@router.get("/{case_id}")
async def read(case: OwnedCase) -> dict[str, Any]:
    return svc.case_view(case)


@router.delete("/{case_id}", status_code=204)
async def delete(case: OwnedCase, session: Db, config: Config) -> Response:
    await svc.delete_case(session, case, config.storage_dir)
    return Response(status_code=204)


@router.put("/{case_id}/authority")
async def authority(
    body: svc.AuthorityInput, case: OwnedCase, user: CurrentUser, session: Db
) -> dict[str, Any]:
    await svc.set_authority(session, case, body)
    return svc.case_view(await svc.get_case(session, user, case.id))


@router.put("/{case_id}/applicant", status_code=204)
async def applicant(body: svc.ApplicantInput, case: OwnedCase, session: Db) -> Response:
    await svc.set_applicant(session, case, body)
    return Response(status_code=204)


@router.post("/{case_id}/questions", status_code=201)
async def add_question(
    body: QuestionText, case: OwnedCase, session: Db, request: Request, _: ModelQuota
) -> dict[str, Any]:
    question = await svc.add_question(session, case, request.app.state.llm, body.text)
    return svc.question_view(question)


@router.patch("/{case_id}/questions/{question_id}")
async def edit_question(
    question_id: str, body: QuestionPatch, case: OwnedCase, session: Db
) -> dict[str, Any]:
    question = await svc.update_question(
        session, case, question_id, rewritten_text=body.rewritten_text, accepted=body.accepted
    )
    return svc.question_view(question)


@router.delete("/{case_id}/questions/{question_id}", status_code=204)
async def remove_question(question_id: str, case: OwnedCase, session: Db) -> Response:
    await svc.delete_question(session, case, question_id)
    return Response(status_code=204)


@router.get("/{case_id}/validation")
async def validation(case: OwnedCase) -> dict[str, Any]:
    return {"flags": [flag.model_dump() for flag in svc.check(case)]}


@router.post("/{case_id}/filing")
async def filing(
    body: svc.FilingInput, case: OwnedCase, user: CurrentUser, session: Db
) -> dict[str, Any]:
    await svc.file_case(session, case, body)
    return svc.case_view(await svc.get_case(session, user, case.id))


class ReplyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    received_on: date


@router.post("/{case_id}/reply")
async def reply(
    body: ReplyInput, case: OwnedCase, user: CurrentUser, session: Db
) -> dict[str, Any]:
    await svc.record_reply(session, case, body.received_on)
    return svc.case_view(await svc.get_case(session, user, case.id))


@router.post("/{case_id}/close")
async def close(case: OwnedCase, user: CurrentUser, session: Db) -> dict[str, Any]:
    await svc.close_case(session, case)
    return svc.case_view(await svc.get_case(session, user, case.id))


class ApplicationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payment_mode: str
    place: str = ""


@router.post("/{case_id}/application")
async def application(
    body: ApplicationInput,
    case: OwnedCase,
    session: Db,
    config: Config,
    request: Request,
    _: ModelQuota,
) -> Response:
    """FR-5: the application PDF (409 blocked while mandatory fields are missing)."""
    pdf = await svc.build_application(
        session,
        case,
        request.app.state.llm,
        request.app.state.renderer,
        config.storage_dir,
        payment_mode=body.payment_mode,
        place=body.place,
    )
    disposition = 'attachment; filename="rti-application.pdf"'
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": disposition})
