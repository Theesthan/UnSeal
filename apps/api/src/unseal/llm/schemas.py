"""Output schemas for the harness's language steps (draft v1, shaped by the Tamil and Hindi eval).

Every model is sent to BharatCode as a strict JSON schema (`llm.client.strict_schema`), so: no
free-form dict fields, and optional values are `X | None` (the model must still emit them).
`USER_FACING` names the fields shown to the user, which must be in the user's language.
"""

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict


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


class Rewrite(StepOutput):
    """One citizen question rewritten into a request for records the authority holds."""

    USER_FACING = ("rewritten", "records_requested", "reason", "suggestion")
    rewritten: str  # empty when the question is refused as third-party personal information
    records_requested: list[str]
    reason: str
    personal_information: bool
    suggestion: str | None


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


class AppealFacts(StepOutput):
    """The facts paragraph of a first appeal; grounds and citations come from code."""

    USER_FACING = ("facts_paragraph",)
    facts_paragraph: str


STEP_SCHEMAS: dict[str, type[StepOutput]] = {
    "rewrite": Rewrite,
    "intake": Intake,
    "compose": Compose,
    "appeal_facts": AppealFacts,
}
