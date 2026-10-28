"""Output schemas for the harness's language steps (draft v1, shaped by the Tamil and Hindi eval).

Every model is sent to BharatCode as a strict JSON schema (`llm.client.strict_schema`), so: no
free-form dict fields, and optional values are `X | None` (the model must still emit them).
`USER_FACING` names the fields shown to the user, which must be in the user's language.
Value rules the JSON schema cannot express (for example "records unless refused") are model
validators: the client's validation rejects a breach and retries once, like any schema failure.
"""

from datetime import date
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StepOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    USER_FACING: ClassVar[tuple[str, ...]] = ()

    def user_text(self) -> str:
        """The text a user will read, one line per non-empty value."""
        parts: list[str] = []
        for name in self.USER_FACING:
            value = getattr(self, name)
            parts.extend(item for item in (value if isinstance(value, list) else [value]) if item)
        return "\n".join(parts)


def _filled(*values: str) -> bool:
    return all(value.strip() for value in values)


class Rewrite(StepOutput):
    """One citizen question rewritten into a request for records the authority holds."""

    USER_FACING = ("rewritten", "records_requested", "reason", "suggestion")
    rewritten: str  # empty when the question is refused as third-party personal information
    records_requested: list[str]
    reason: str
    personal_information: bool
    suggestion: str | None

    @model_validator(mode="after")
    def _records_unless_refused(self) -> Self:
        if not _filled(self.reason):
            raise ValueError("reason is empty")
        if self.personal_information and (self.rewritten.strip() or self.records_requested):
            raise ValueError("a personal-information refusal must not request the data")
        if not self.personal_information and not (
            _filled(self.rewritten) and self.records_requested and _filled(*self.records_requested)
        ):
            raise ValueError("a rewrite must name the records it requests")
        return self


class Intake(StepOutput):
    """Facts for an application, extracted from the citizen's own words."""

    USER_FACING = ("follow_up_questions",)
    jurisdiction_hint: Literal["central", "tamil_nadu", "other", "unknown"]
    authority: str | None
    time_period: str | None
    records_wanted: list[str]
    delivery_mode: Literal["post", "email", "in_person", "unknown"]
    bpl: Literal["yes", "no", "unknown"]
    follow_up_questions: list[str]
    ready_to_draft: bool


class Compose(StepOutput):
    """Subject line and questions; the template adds numbering, names, addresses and law."""

    USER_FACING = ("subject", "questions")
    subject: str
    questions: list[str]

    @model_validator(mode="after")
    def _has_content(self) -> Self:
        if not (_filled(self.subject) and self.questions and _filled(*self.questions)):
            raise ValueError("subject and every question must have text")
        return self


class AppealFacts(StepOutput):
    """The facts paragraph of a first appeal; grounds and citations come from code."""

    USER_FACING = ("facts_paragraph",)
    facts_paragraph: str

    @model_validator(mode="after")
    def _has_content(self) -> Self:
        if not _filled(self.facts_paragraph):
            raise ValueError("facts_paragraph is empty")
        return self


class ReplyItem(BaseModel):
    """One numbered point of the application, as the PIO's reply answers it."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    number: int = Field(ge=1)
    status: Literal["given", "refused", "partial", "transferred", "unclear"]
    section_cited: str | None = Field(max_length=40)  # as printed, for example "8(1)(j)"


class ReplyRead(StepOutput):
    """What a PIO's reply letter says, read from its photo (FR-11). Only these fields are kept:
    nothing else on the letter (names, addresses, signatures) is asked for or stored."""

    letter_date: str | None  # YYYY-MM-DD as printed on the letter; None when there is none
    items: list[ReplyItem]
    fee_demanded: bool
    transferred_to: str | None = Field(max_length=200)

    @model_validator(mode="after")
    def _well_formed(self) -> Self:
        if self.letter_date is not None:
            date.fromisoformat(self.letter_date)  # ValueError: not YYYY-MM-DD
        numbers = [item.number for item in self.items]
        if len(set(numbers)) != len(numbers):
            raise ValueError("an item number is repeated")
        return self


STEP_SCHEMAS: dict[str, type[StepOutput]] = {
    "rewrite": Rewrite,
    "intake": Intake,
    "compose": Compose,
    "appeal_facts": AppealFacts,
}
