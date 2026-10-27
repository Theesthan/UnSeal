"""Case routes (docs/api.md "Cases"). Thin: parse, call services.cases, shape the response."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from unseal.api.deps import Config, CurrentUser, Db, LanguageCode
from unseal.api.errors import ApiError
from unseal.api.ratelimit import ModelQuota
from unseal.db.models import Case
from unseal.rules.engine import Jurisdiction
from unseal.services import appeals, reply_reader
from unseal.services import cases as svc
from unseal.services.intake import run_intake

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


class IntakeMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=4000)


@router.post("/{case_id}/intake")
async def intake(
    body: IntakeMessage, case: OwnedCase, request: Request, _: ModelQuota
) -> dict[str, Any]:
    """FR-1 facts and FR-4 authority candidates; nothing is stored until the user confirms."""
    llm = request.app.state.llm
    result = await run_intake(llm, body.message, language=case.language)  # type: ignore[arg-type]
    return result.model_dump()


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


class ReceiptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    received_on: date


@router.put("/{case_id}/receipt")
async def receipt(
    body: ReceiptInput, case: OwnedCase, user: CurrentUser, session: Db
) -> dict[str, Any]:
    """The actual day the authority received the application (from the postal tracking or the
    acknowledgement): deadlines restart from it and stop being estimates."""
    await svc.set_receipt(session, case, body.received_on)
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


@router.post("/{case_id}/appeal")
async def appeal(
    body: appeals.AppealInput, case: OwnedCase, session: Db, config: Config, request: Request
) -> Response:
    """FR-10: the first appeal PDF (no model call, so no model quota)."""
    pdf = await appeals.build_first_appeal(
        session, case, request.app.state.appeal_renderer, config.storage_dir, body
    )
    disposition = 'attachment; filename="rti-first-appeal.pdf"'
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": disposition})


@router.post("/{case_id}/appeal/filing")
async def appeal_filing(
    body: appeals.AppealFiling, case: OwnedCase, user: CurrentUser, session: Db
) -> dict[str, Any]:
    await appeals.file_first_appeal(session, case, body)
    return svc.case_view(await svc.get_case(session, user, case.id))


async def _upload(request: Request) -> bytes:
    """The `file` of a multipart form with `consent=true`. The size is checked from the
    Content-Length header before the body is parsed, so an oversized upload is never spooled."""
    length = request.headers.get("content-length")
    if length is None or not length.isdigit():
        raise ApiError(411, "length_required")
    if int(length) > reply_reader.MAX_UPLOAD_BYTES + 64 * 1024:  # room for the form framing
        raise ApiError(413, "too_large")
    async with request.form(max_files=1, max_fields=2) as form:
        if form.get("consent") != "true":
            raise ApiError(400, "consent_required")
        upload = form.get("file")
        if upload is None or isinstance(upload, str):
            raise ApiError(400, "invalid")
        data = await upload.read(reply_reader.MAX_UPLOAD_BYTES + 1)
    if len(data) > reply_reader.MAX_UPLOAD_BYTES:
        raise ApiError(413, "too_large")
    return data


@router.post("/{case_id}/reply/read")
async def read_reply(case: OwnedCase, request: Request, _: ModelQuota) -> dict[str, Any]:
    """FR-11: read a photo or PDF of the PIO's reply (multipart `file`, `consent=true`).
    Nothing is stored: the user confirms the date through POST /reply."""
    reply_reader.ensure_readable(case)
    found = await reply_reader.read_case_reply(request.app.state.llm, case, await _upload(request))
    return {
        "letter_date": found.letter_date.isoformat() if found.letter_date else None,
        "items": [item.model_dump() for item in found.reading.items],
        "fee_demanded": found.reading.fee_demanded,
        "transferred_to": found.reading.transferred_to,
        "suggested_grounds": found.suggested_grounds,
    }
