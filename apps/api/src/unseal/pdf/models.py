"""Input to the application renderer.

The harness fills this from the validated rewrite (subject, questions) and the case record (names,
addresses). Fees and payment rules are not here: the renderer reads them from the rules engine.
"""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ApplicationDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    language: Literal["en", "hi", "ta"]
    jurisdiction: Literal["central", "tamil_nadu"]
    authority_name: NonBlank
    pio_address: NonBlank  # a missing PIO or applicant address blocks export (CLAUDE.md)
    applicant_name: NonBlank
    applicant_address: NonBlank
    subject: NonBlank
    questions: list[str] = Field(min_length=1)
    bpl: bool
    payment_mode: str | None  # a code from the rules' payment_modes, or text as the user wrote it
    prepared_on: date
    place: str  # may be blank: the Place row is then left out

    @field_validator("questions")
    @classmethod
    def _no_blank_question(cls, questions: list[str]) -> list[str]:
        if any(not q.strip() for q in questions):
            raise ValueError("a question is blank")
        return questions
