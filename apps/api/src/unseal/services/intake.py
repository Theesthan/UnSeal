"""Intake service (FR-1, FR-4): one citizen message to extracted facts plus authority candidates.

The model extracts the facts; the candidates come only from the curated list
(rules/data/authorities.json), never from the model, and the user confirms one (FR-4).
"""

from typing import get_args

from pydantic import BaseModel, ConfigDict

from unseal.harness import steps
from unseal.harness.steps import StructuredLLM
from unseal.llm.glossary import Language
from unseal.llm.schemas import Intake
from unseal.rules.authorities import Authority, lookup_authority
from unseal.rules.engine import Jurisdiction

MAX_CANDIDATES = 3


class AuthorityCandidate(BaseModel):
    """What the user sees to pick an authority: no provenance fields (docs/api.md)."""

    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    name_ta: str | None
    name_hi: str | None
    jurisdiction: str
    pio_designation: str
    pio_address: str
    rti_online: bool | None  # None: not checked

    @classmethod
    def of(cls, authority: Authority) -> "AuthorityCandidate":
        return cls.model_validate(authority.model_dump(include=set(cls.model_fields)))


class IntakeResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    intake: Intake
    authorities: list[AuthorityCandidate]


def suggest_authorities(facts: Intake) -> list[AuthorityCandidate]:
    """Candidates for the named authority, else for the first record that matches any."""
    hint = facts.jurisdiction_hint
    jurisdiction = hint if hint in get_args(Jurisdiction) else None
    for query in (facts.authority, *facts.records_wanted):
        if query and (found := lookup_authority(query, jurisdiction, MAX_CANDIDATES)):
            return [AuthorityCandidate.of(authority) for authority in found]
    return []


async def run_intake(llm: StructuredLLM, message: str, *, language: Language) -> IntakeResult:
    facts = await steps.intake(llm, message, language=language)
    return IntakeResult(intake=facts, authorities=suggest_authorities(facts))
