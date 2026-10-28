"""Input to the application renderer.

The harness fills this from the validated rewrite (subject, questions) and the case record (names,
addresses). Fees and payment rules are not here: the renderer reads them from the rules engine.
"""

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

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


Ground = Literal["no_reply", "incomplete", "refused", "fee_demanded"]
FilingMode = Literal["rti_online", "post", "in_person"]


class AppealDocument(BaseModel):
    """Input to the first appeal renderer (FR-10, S. 19(1)).

    Every date and the filing mode come from the case record and the rules engine; the facts and
    grounds are fixed template text per language, so no model writes this letter. `details` and
    `delay_reason` are the appellant's own words, printed as given. Section numbers come from
    `load_rules(jurisdiction)` at render time, never from here.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    language: Literal["en", "hi", "ta"]
    jurisdiction: Literal["central", "tamil_nadu"]
    authority_name: NonBlank
    pio_address: NonBlank  # the respondent PIO
    faa_address: NonBlank  # the First Appellate Authority, as the appellant confirmed it
    appellant_name: NonBlank
    appellant_address: NonBlank
    filed_on: date
    filing_mode: FilingMode
    received_on: date  # the engine's day 0: actual receipt, or filed_on plus the transit buffer
    received_estimated: bool
    reply_due_on: date
    reply_received_on: date | None  # None: no reply (deemed refusal)
    grounds: list[Ground] = Field(min_length=1)
    details: str  # may be blank
    late: bool  # filed after the S. 19(1) window; the delay paragraph is then printed
    delay_reason: str  # may be blank; printed only when late
    prepared_on: date
    place: str  # may be blank: the Place row is then left out

    @field_validator("grounds")
    @classmethod
    def _unique_grounds(cls, grounds: list[Ground]) -> list[Ground]:
        if len(set(grounds)) != len(grounds):
            raise ValueError("a ground is repeated")
        return grounds

    @model_validator(mode="after")
    def _no_reply_means_no_reply(self) -> Self:
        if "no_reply" in self.grounds and self.reply_received_on is not None:
            raise ValueError("no_reply cannot be a ground once a reply was received")
        return self


SecondGround = Literal[
    "no_reply", "no_decision", "refused", "incomplete", "incorrect", "fee_demanded"
]


class SecondAppealDocument(BaseModel):
    """Input to the second appeal renderer (FR-12, S. 19(3)).

    The format (CIC rule 8 Appendix or the TNSIC form) and the list of copies to enclose come
    from `load_rules(jurisdiction).local.second_appeal_format` at render time; the renderer drops
    the copies this case cannot have (no reply, no order, no transfer). Like the first appeal,
    no model writes this letter: dates, filing mode and grounds are code-owned template text, and
    `details` and `delay_reason` are the appellant's own words. Fields a format asks for that
    UnSeal does not hold (a guardian's name, a missing phone) are printed blank to fill by hand.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    language: Literal["en", "hi", "ta"]
    jurisdiction: Literal["central", "tamil_nadu"]
    authority_name: NonBlank
    pio_address: NonBlank
    faa_address: NonBlank
    appellant_name: NonBlank
    appellant_address: NonBlank
    appellant_phone: str | None  # the TNSIC form marks it mandatory: blank when unknown
    filed_on: date
    filing_mode: FilingMode
    received_on: date
    received_estimated: bool
    reply_due_on: date
    reply_received_on: date | None
    transferred_to: str | None  # S. 6(3) transfer, when the case records one
    appeal_filed_on: date  # the first appeal
    faa_decision_received_on: date | None  # None: the appellate authority passed no order
    grounds: list[SecondGround] = Field(min_length=1)
    details: str  # may be blank
    hearing_mode: Literal["virtual", "direct"] | None  # TNSIC form only; None prints both boxes
    late: bool
    delay_reason: str  # may be blank; printed only when late
    prepared_on: date
    place: str

    @field_validator("grounds")
    @classmethod
    def _unique_grounds(cls, grounds: list[SecondGround]) -> list[SecondGround]:
        if len(set(grounds)) != len(grounds):
            raise ValueError("a ground is repeated")
        return grounds

    @model_validator(mode="after")
    def _grounds_fit_the_case(self) -> Self:
        if "no_reply" in self.grounds and self.reply_received_on is not None:
            raise ValueError("no_reply cannot be a ground once a reply was received")
        if "no_decision" in self.grounds and self.faa_decision_received_on is not None:
            raise ValueError("no_decision cannot be a ground once the order was received")
        return self
