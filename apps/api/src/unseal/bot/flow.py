"""Drafting on Telegram (FR-1, FR-2, FR-4): describe the problem, answer at most two follow-ups,
confirm the authority, then review each rewritten question."""

from typing import Any, cast, get_args

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ConversationHandler

from unseal.bot.common import (
    MAX_ADDRESS,
    MAX_ANSWER,
    MAX_DESCRIPTION,
    MAX_NAME,
    MAX_QUESTION,
    Ctx,
    S,
    button,
    clear_flow,
    current_user,
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
from unseal.bot.texts import TEXTS, Language, t, term
from unseal.rules.engine import Jurisdiction, Rules, load_rules
from unseal.services import intake as intake_service
from unseal.services.cases import (
    AuthorityInput,
    add_question,
    create_case,
    question_view,
    set_authority,
    update_question,
)
from unseal.services.intake import AuthorityCandidate

MAX_FOLLOW_UPS = 2
MAX_CANDIDATES = 3
_ONLINE = {True: "rti_online_yes", False: "rti_online_no", None: "rti_online_unknown"}


def rules_for(jurisdiction: str) -> Rules:
    """Rules for a stored jurisdiction (validated against the rules data by `load_rules`)."""
    return load_rules(cast(Jurisdiction, jurisdiction))


def jurisdiction_of(value: object) -> str | None:
    return value if isinstance(value, str) and value in get_args(Jurisdiction) else None


def display_name(candidate: AuthorityCandidate, language: Language) -> str:
    local = {"ta": candidate.name_ta, "hi": candidate.name_hi}.get(language)
    return local or candidate.name


def flag_items(codes: list[str], language: Language) -> str:
    """Blocking flags as a bulleted list in the user's language."""
    lines = []
    for code in codes:
        key = f"flag_{code}"
        lines.append("- " + (t(key, language) if key in TEXTS else t("flag_other", language)))
    return "\n".join(lines)


# ---------------------------------------------------------------- describe and follow-ups


async def describe(update: Update, context: Ctx) -> int:
    text = await take_text(update, context, MAX_DESCRIPTION)
    if text is None:
        return S.DESCRIBE
    return await intake_step(update, context, text)


async def intake_step(update: Update, context: Ctx, text: str) -> int:
    async def action() -> int:
        result = await intake_service.run_intake(
            services(context).llm, text, language=lang(context)
        )
        store = data(context)
        store["request"] = [text]
        store["candidates"] = list(result.authorities[:MAX_CANDIDATES])
        store["hint"] = result.intake.jurisdiction_hint
        questions = [q.strip() for q in result.intake.follow_up_questions if q.strip()]
        store["followups"] = questions[:MAX_FOLLOW_UPS]
        return await ask_next(update, context)

    pending = {"kind": "intake", "text": text}
    return await guarded(
        update, context, pending=pending, stay=S.DESCRIBE, invalid_key="rephrase", action=action
    )


async def ask_next(update: Update, context: Ctx) -> int:
    followups: list[str] = data(context).get("followups", [])
    if followups:
        await send(update, context, followups[0])
        return S.FOLLOW_UP
    return await show_authorities(update, context)


async def follow_up(update: Update, context: Ctx) -> int:
    answer = await take_text(update, context, MAX_ANSWER)
    if answer is None:
        return S.FOLLOW_UP
    store = data(context)
    question, *rest = store["followups"]
    store["request"] = [*store["request"], f"{question} {answer}"]
    store["followups"] = rest
    return await ask_next(update, context)


# ---------------------------------------------------------------- authority (FR-4)


async def show_authorities(update: Update, context: Ctx) -> int:
    language = lang(context)
    candidates: list[AuthorityCandidate] = data(context).get("candidates", [])
    rows = [[(display_name(c, language), f"auth:{i}")] for i, c in enumerate(candidates)]
    rows.append([button(context, "other", "auth:other")])
    await say(update, context, "choose_authority", keyboard(rows))
    return S.AUTHORITY


async def pick_authority(update: Update, context: Ctx) -> int:
    code = (await tapped(update)).removeprefix("auth:")
    store = data(context)
    if code == "other":
        await say(update, context, "authority_name")
        return S.AUTHORITY_NAME
    candidates: list[AuthorityCandidate] = store.get("candidates", [])
    index = int(code)
    if index >= len(candidates):
        return await show_authorities(update, context)
    candidate = candidates[index]
    store["choice"] = {
        "name": display_name(candidate, lang(context)),
        "designation": candidate.pio_designation,
        "address": candidate.pio_address,
        "online": _ONLINE[candidate.rti_online],
        "jurisdiction": jurisdiction_of(candidate.jurisdiction)
        or jurisdiction_of(store.get("hint")),
    }
    return await confirm_or_ask_jurisdiction(update, context)


async def authority_name(update: Update, context: Ctx) -> int:
    name = await take_text(update, context, MAX_NAME)
    if name is None:
        return S.AUTHORITY_NAME
    data(context)["other_name"] = name
    await say(update, context, "authority_address")
    return S.AUTHORITY_ADDRESS


async def authority_address(update: Update, context: Ctx) -> int:
    address = await take_text(update, context, MAX_ADDRESS)
    if address is None:
        return S.AUTHORITY_ADDRESS
    store = data(context)
    store["choice"] = {
        "name": store.get("other_name", ""),
        "designation": term("pio", lang(context)),
        "address": address,
        "online": _ONLINE[None],
        "jurisdiction": jurisdiction_of(store.get("hint")),
    }
    return await confirm_or_ask_jurisdiction(update, context)


async def confirm_or_ask_jurisdiction(update: Update, context: Ctx) -> int:
    choice: dict[str, Any] = data(context)["choice"]
    if choice["jurisdiction"] is None:
        rows = [
            [button(context, "jur_central", "jur:central")],
            [button(context, "jur_tamil_nadu", "jur:tamil_nadu")],
        ]
        await say(update, context, "choose_jurisdiction", keyboard(rows))
        return S.JURISDICTION
    return await show_confirm(update, context)


async def pick_jurisdiction(update: Update, context: Ctx) -> int:
    code = (await tapped(update)).removeprefix("jur:")
    store = data(context)
    if "choice" not in store:
        return await show_authorities(update, context)
    store["choice"] = {**store["choice"], "jurisdiction": jurisdiction_of(code)}
    return await confirm_or_ask_jurisdiction(update, context)


async def show_confirm(update: Update, context: Ctx) -> int:
    choice: dict[str, Any] = data(context)["choice"]
    rows = [[button(context, "confirm", "authok"), button(context, "change", "authchange")]]
    await say(
        update,
        context,
        "confirm_authority",
        keyboard(rows),
        designation=choice["designation"],
        name=choice["name"],
        address=choice["address"],
        online=t(choice["online"], lang(context)),
    )
    return S.CONFIRM


async def change_authority(update: Update, context: Ctx) -> int:
    await tapped(update)
    return await show_authorities(update, context)


async def confirm_authority(update: Update, context: Ctx) -> int:
    await tapped(update)
    store = data(context)
    choice: dict[str, Any] | None = store.get("choice")
    if choice is None:
        return await show_authorities(update, context)
    async with services(context).session_factory() as session:
        user = await current_user(session, update, context)
        if user is None:
            await say(update, context, "need_start")
            clear_flow(context)
            return ConversationHandler.END
        case = await create_case(
            session, user, language=lang(context), jurisdiction=choice["jurisdiction"]
        )
        authority = AuthorityInput(
            jurisdiction=choice["jurisdiction"],
            authority_name=choice["name"],
            pio_address=choice["address"],
        )
        await set_authority(session, case, authority)
    store["case_id"] = case.id
    return await question_step(update, context, "\n".join(store.get("request", [])))


# ---------------------------------------------------------------- questions (FR-2, FR-3)


async def question_step(update: Update, context: Ctx, text: str) -> int:
    async def action() -> int:
        async with services(context).session_factory() as session:
            case = await load_case(session, update, context)
            question = await add_question(session, case, services(context).llm, text)
            basis = rules_for(case.jurisdiction).act.personal_information.basis
        view = question_view(question)
        language = lang(context)
        await send(update, context, question_text(view, basis, language), buttons(context, view))
        return S.REVIEW

    pending = {"kind": "question", "text": text}
    return await guarded(
        update, context, pending=pending, stay=S.NEW_QUESTION, invalid_key="rephrase", action=action
    )


def question_text(view: dict[str, Any], basis: str, language: Language) -> str:
    if view["personal_information"]:
        lines = [t("personal_info", language, basis=basis)]
        if view["suggestion"]:
            lines.append(t("suggestion", language, suggestion=view["suggestion"]))
        return "\n\n".join(lines)
    return t("rewritten", language, text=view["rewritten_text"] or "", reason=view["reason"] or "")


def buttons(context: Ctx, view: dict[str, Any], *, accepted: bool = False) -> InlineKeyboardMarkup:
    """Accept and Edit only for a usable rewrite; question ids are opaque UUIDs."""
    rows = []
    if not view["personal_information"] and not accepted:
        rows.append(
            [
                button(context, "accept", f"q:accept:{view['id']}"),
                button(context, "edit", f"q:edit:{view['id']}"),
            ]
        )
    rows += [[button(context, "add", "q:add")], [button(context, "done", "q:done")]]
    return keyboard(rows)


async def accept(update: Update, context: Ctx) -> int:
    question_id = (await tapped(update)).removeprefix("q:accept:")
    async with services(context).session_factory() as session:
        case = await load_case(session, update, context)
        question = await update_question(session, case, question_id, accepted=True)
        basis = rules_for(case.jurisdiction).act.personal_information.basis
    view = question_view(question)
    language = lang(context)
    text = question_text(view, basis, language) + "\n\n" + t("accepted", language)
    query = update.callback_query
    assert query is not None
    await query.edit_message_text(text, reply_markup=buttons(context, view, accepted=True))
    return S.REVIEW


async def edit(update: Update, context: Ctx) -> int:
    data(context)["editing"] = (await tapped(update)).removeprefix("q:edit:")
    await say(update, context, "edit_prompt")
    return S.EDIT


async def edited(update: Update, context: Ctx) -> int:
    text = await take_text(update, context, MAX_QUESTION)
    if text is None:
        return S.EDIT
    question_id = str(data(context).get("editing", ""))
    async with services(context).session_factory() as session:
        case = await load_case(session, update, context)
        await update_question(session, case, question_id, rewritten_text=text, accepted=True)
    rows = [[button(context, "add", "q:add")], [button(context, "done", "q:done")]]
    await say(update, context, "saved_edit", keyboard(rows))
    return S.REVIEW


async def add(update: Update, context: Ctx) -> int:
    await tapped(update)
    await say(update, context, "add_prompt")
    return S.NEW_QUESTION


async def new_question(update: Update, context: Ctx) -> int:
    text = await take_text(update, context, MAX_QUESTION)
    if text is None:
        return S.NEW_QUESTION
    return await question_step(update, context, text)


async def done(update: Update, context: Ctx) -> int:
    """On to the applicant, unless no question asks for records (it would block export)."""
    await tapped(update)
    async with services(context).session_factory() as session:
        case = await load_case(session, update, context)
    if not any(not q.personal_information for q in case.questions):
        items = flag_items(["no_questions"], lang(context))
        rows = [[button(context, "add", "q:add")]]
        await say(update, context, "blocked", keyboard(rows), items=items)
        return S.REVIEW
    await say(update, context, "ask_name")
    return S.NAME
