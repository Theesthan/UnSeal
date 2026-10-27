"""Finishing on Telegram (FR-5 to FR-7): applicant details, payment mode, the PDF with a filing
checklist, then the filing date and the deadlines. Applicant details are stored encrypted by the
service layer and never repeated back in chat."""

import re
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InputFile, Update
from telegram.ext import ConversationHandler

from unseal.bot.common import (
    MAX_ADDRESS,
    MAX_NAME,
    MAX_PLACE,
    Ctx,
    S,
    button,
    chat_id,
    clear_flow,
    data,
    guarded,
    keyboard,
    lang,
    load_case,
    say,
    send,
    services,
    take_text,
    tapped,
)
from unseal.bot.flow import flag_items, rules_for
from unseal.bot.texts import TEXTS, TODAY_WORDS, Language, footer, format_date, t
from unseal.db.models import Case, Deadline
from unseal.pdf.labels import labels_for
from unseal.rules.engine import Rules
from unseal.services import cases as case_service
from unseal.services.cases import (
    ApplicantInput,
    Blocked,
    FilingInput,
    InvalidPaymentMode,
    WrongStatus,
    file_case,
    set_applicant,
)

PDF_NAME = "rti-application.pdf"
FILING_MODES = ("rti_online", "post", "in_person")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


# ---------------------------------------------------------------- applicant


async def save_applicant(session: AsyncSession, case: Case, **changes: object) -> None:
    """Change some applicant fields, keeping the rest (stored encrypted, one per case)."""
    current = case.applicant
    base: dict[str, object] = (
        {
            "name": current.name,
            "address": current.address or "",
            "phone": current.phone,
            "bpl": current.bpl,
        }
        if current
        else {"name": "", "address": "", "phone": None, "bpl": False}
    )
    await set_applicant(session, case, ApplicantInput.model_validate({**base, **changes}))


async def applicant_name(update: Update, context: Ctx) -> int:
    name = await take_text(update, context, MAX_NAME)
    if name is None:
        return S.NAME
    async with services(context).session_factory() as session:
        case = await case_for(session, update, context)
        await save_applicant(session, case, name=name)
    await say(update, context, "ask_address")
    return S.ADDRESS


async def applicant_address(update: Update, context: Ctx) -> int:
    address = await take_text(update, context, MAX_ADDRESS)
    if address is None:
        return S.ADDRESS
    async with services(context).session_factory() as session:
        case = await case_for(session, update, context)
        await save_applicant(session, case, address=address)
    rows = [[button(context, "yes", "bpl:yes"), button(context, "no", "bpl:no")]]
    await say(update, context, "ask_bpl", keyboard(rows))
    return S.BPL


async def bpl(update: Update, context: Ctx) -> int:
    below_poverty_line = (await tapped(update)) == "bpl:yes"
    async with services(context).session_factory() as session:
        case = await case_for(session, update, context)
        await save_applicant(session, case, bpl=below_poverty_line)
    if below_poverty_line:  # S. 7(5): no fee, so no payment mode
        data(context)["payment_mode"] = ""
        await say(update, context, "ask_place")
        return S.PLACE
    return await ask_payment(update, context, case.jurisdiction)


async def case_for(session: AsyncSession, update: Update, context: Ctx) -> Case:
    return await load_case(session, update, context)


# ---------------------------------------------------------------- payment and the PDF


async def ask_payment(update: Update, context: Ctx, jurisdiction: str) -> int:
    rules = rules_for(jurisdiction)
    labels = labels_for(lang(context)).payment_modes
    rows = [[(labels.get(mode, mode), f"pay:{mode}")] for mode in rules.local.payment_modes.modes]
    fee = rules.local.application_fee.rupees
    await say(update, context, "ask_payment", keyboard(rows), fee=fee)
    return S.PAYMENT


async def payment(update: Update, context: Ctx) -> int:
    mode = (await tapped(update)).removeprefix("pay:")
    async with services(context).session_factory() as session:
        case = await case_for(session, update, context)
    if mode not in rules_for(case.jurisdiction).local.payment_modes.modes:
        return await ask_payment(update, context, case.jurisdiction)  # a forged or stale button
    data(context)["payment_mode"] = mode
    await say(update, context, "ask_place")
    return S.PLACE


async def place(update: Update, context: Ctx) -> int:
    text = await take_text(update, context, MAX_PLACE)
    if text is None:
        return S.PLACE
    return await application_step(update, context, text)


async def application_step(update: Update, context: Ctx, place: str) -> int:
    async def action() -> int:
        svc, language = services(context), lang(context)
        async with svc.session_factory() as session:
            case = await case_for(session, update, context)
            try:
                pdf = await case_service.build_application(
                    session,
                    case,
                    svc.llm,
                    svc.renderer,
                    svc.settings.storage_dir,
                    payment_mode=str(data(context).get("payment_mode", "")),
                    place=place,
                )
            except Blocked as blocked:
                items = flag_items([flag.code for flag in blocked.flags], language)
                rows = [[button(context, "add", "q:add")]]
                await say(update, context, "blocked", keyboard(rows), items=items)
                return S.REVIEW
            except InvalidPaymentMode:
                return await ask_payment(update, context, case.jurisdiction)
            rules = rules_for(case.jurisdiction)
            is_bpl = bool(case.applicant and case.applicant.bpl)
        document = InputFile(pdf, filename=PDF_NAME)
        caption = t("pdf_caption", language)
        await context.bot.send_document(chat_id(update), document, caption=caption)
        await send(update, context, checklist(language, rules, bpl=is_bpl))
        await say(update, context, "ask_filed")
        return S.FILED_DATE

    pending = {"kind": "application", "place": place}
    return await guarded(
        update, context, pending=pending, stay=S.PLACE, invalid_key="try_again", action=action
    )


def checklist(language: Language, rules: Rules, *, bpl: bool) -> str:
    """Where to send it, the fee and payment modes (from the rules), what to keep as proof."""
    local = rules.local
    if bpl:
        fee = t("fee_bpl", language)
        if local.bpl_certificate_required.applies:
            fee += " " + t("bpl_copy", language)
    else:
        labels = labels_for(language).payment_modes
        modes = ", ".join(labels.get(mode, mode) for mode in local.payment_modes.modes)
        fee = t("check_fee", language, fee=local.application_fee.rupees, modes=modes)
    channels = ", ".join(
        t(f"channel_{c}", language) if f"channel_{c}" in TEXTS else c
        for c in local.filing_channels.channels
    )
    steps = [
        t("check_sign", language),
        fee,
        t("check_send", language, channels=channels),
        t("check_proof", language),
        t("check_confirm", language),
    ]
    numbered = [f"{n}. {step}" for n, step in enumerate(steps, start=1)]
    return "\n".join([t("check_header", language), *numbered, "", footer(language)])


# ---------------------------------------------------------------- filing (FR-6, FR-7)


def parse_filed_on(raw: str) -> date | None:
    """`YYYY-MM-DD`, or the word for today in English, Hindi or Tamil."""
    if raw.casefold() in TODAY_WORDS:
        return case_service.today_ist()
    if not _ISO_DATE.fullmatch(raw):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


async def filed_date(update: Update, context: Ctx) -> int:
    raw = await take_text(update, context, 40)
    if raw is None:
        return S.FILED_DATE
    filed_on = parse_filed_on(raw)
    if filed_on is None:
        await say(update, context, "bad_date")
        return S.FILED_DATE
    if filed_on > case_service.today_ist():
        await say(update, context, "future_date")
        return S.FILED_DATE
    data(context)["filed_on"] = filed_on.isoformat()
    rows = [[button(context, f"mode_{mode}", f"mode:{mode}")] for mode in FILING_MODES]
    await say(update, context, "ask_mode", keyboard(rows))
    return S.FILED_MODE


async def filed_mode(update: Update, context: Ctx) -> int:
    mode = (await tapped(update)).removeprefix("mode:")
    filed_on = data(context).get("filed_on")
    if not isinstance(filed_on, str):
        await say(update, context, "ask_filed")
        return S.FILED_DATE
    filing = FilingInput.model_validate({"filed_on": filed_on, "filing_mode": mode})
    async with services(context).session_factory() as session:
        case = await case_for(session, update, context)
        try:
            await file_case(session, case, filing)
        except WrongStatus:
            await say(update, context, "wrong_status")
            clear_flow(context)
            return ConversationHandler.END
        case = await case_for(session, update, context)  # reload with the new deadlines
    await send(update, context, deadlines_text(case, lang(context)))
    clear_flow(context)
    return ConversationHandler.END


def shown_date(day: date, estimated: bool, language: Language) -> str:
    text = format_date(day, language)
    return f"{text} {t('estimated', language)}" if estimated else text


def deadlines_text(case: Case, language: Language) -> str:
    """The PIO reply and first-appeal dates, from the rules engine via the case's deadlines."""
    by_kind: dict[str, Deadline] = {d.kind: d for d in case.deadlines}
    pio, appeal = by_kind["pio_reply"], by_kind["first_appeal"]
    assert case.filed_on is not None
    text = t(
        "deadlines",
        language,
        filed=format_date(case.filed_on, language),
        pio_reply=shown_date(pio.due_on, pio.estimated, language),
        appeal=shown_date(appeal.due_on, appeal.estimated, language),
    )
    if case.received_estimated and case.received_on:
        days = (case.received_on - case.filed_on).days
        text += "\n\n" + t("estimated_note", language, days=days)
    return text
