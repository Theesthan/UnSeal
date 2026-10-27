"""FR-3 validator: code checks on a draft before export.

Only missing mandatory fields block export (PRD FR-3); everything else warns. Limits and legal
bases come from the rules engine. Flags carry codes, not sentences: the web app and the bot word
them in the user's language.
"""

import re
from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel, ConfigDict

from unseal.rules.engine import Jurisdiction, Rules, load_rules

Severity = Literal["warn", "block"]

# "why" in English, Tamil and Hindi. क्योंकि ("because") is not a question.
_WHY = re.compile(r"\bwhy\b|ஏன்|क्यों(?!कि)", re.IGNORECASE)


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    jurisdiction: Jurisdiction
    questions: tuple[str, ...]
    personal_information: bool  # any rewrite flagged third-party personal information
    pio_address: str
    applicant_address: str


class Flag(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    code: str
    severity: Severity
    question: int | None = None  # index into Draft.questions, when the flag is about one
    basis: str | None = None
    under_challenge: bool = False


def validate(draft: Draft) -> tuple[Flag, ...]:
    rules = load_rules(draft.jurisdiction)
    return (
        *_missing(draft),
        *_length(draft, rules),
        *_personal_information(draft, rules),
        *_opinion_asks(draft),
    )


def _missing(draft: Draft) -> Iterator[Flag]:
    if not draft.pio_address.strip():
        yield Flag(code="missing_pio_address", severity="block")
    if not draft.applicant_address.strip():
        yield Flag(code="missing_applicant_address", severity="block")
    if not draft.questions:
        yield Flag(code="no_questions", severity="block")


def _length(draft: Draft, rules: Rules) -> Iterator[Flag]:
    limit = rules.local.word_limit
    if limit is None:
        return
    words = sum(len(question.split()) for question in draft.questions)
    if words > limit.words:
        yield Flag(
            code="over_word_limit",
            severity="block" if limit.blocks_filing else "warn",
            basis=limit.basis,
        )


def _personal_information(draft: Draft, rules: Rules) -> Iterator[Flag]:
    if draft.personal_information:
        rule = rules.act.personal_information
        yield Flag(
            code="personal_information",
            severity="warn",
            basis=rule.basis,
            under_challenge=rule.under_challenge,
        )


def _opinion_asks(draft: Draft) -> Iterator[Flag]:
    for index, question in enumerate(draft.questions):
        if _WHY.search(question):
            yield Flag(code="opinion_ask", severity="warn", question=index)
