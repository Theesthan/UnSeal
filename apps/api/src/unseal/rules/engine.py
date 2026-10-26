"""Rules engine: the only source of legal values (deadlines, fees, sections).

Values live in rules/data/*.json, never in code. rti_act.json holds the statute, which applies to
every jurisdiction; <jurisdiction>.json holds that jurisdiction's own rules (fees, payment modes).
Every rule carries the source it was read from and the day someone opened it.
"""

from datetime import date, timedelta
from functools import cache
from importlib.resources import files
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, PositiveInt

Jurisdiction = Literal["central", "tamil_nadu"]

RECHECK_AFTER_DAYS = 180


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(_Frozen):
    """Provenance: `checked_on` is the day someone opened `source_url` and read `quote`."""

    basis: str = Field(min_length=1)
    source_url: HttpUrl
    checked_on: date
    quote: str = Field(min_length=1)
    under_challenge: bool = False
    note: str | None = None


class Days(Source):
    days: PositiveInt


class Hours(Source):
    hours: PositiveInt


class Rupees(Source):
    rupees: int = Field(ge=0)


class Flag(Source):
    applies: bool


class Appeal(Days):
    late_allowed: bool  # admitted late "if ... prevented by sufficient cause"


class FaaDecision(Days):
    max_days: PositiveInt


class Languages(Source):
    codes: tuple[str, ...] = Field(min_length=1)
    plus_area_official_language: bool


class WordLimit(Source):
    words: PositiveInt
    blocks_filing: bool


class PaymentModes(Source):
    modes: tuple[str, ...] = Field(min_length=1)


class FilingChannels(Source):
    channels: tuple[str, ...] = Field(min_length=1)


class ActRules(_Frozen):
    """RTI Act 2005: the same for every jurisdiction."""

    languages: Languages
    no_reason_needed: Flag
    transfer: Days
    apio_extra: Days
    pio_reply: Days
    life_liberty_reply: Hours
    deemed_refusal: Flag
    bpl_fee_exempt: Flag
    personal_information: Flag
    third_party_reply: Days
    first_appeal: Appeal
    faa_decision: FaaDecision
    second_appeal: Appeal


class LocalRules(_Frozen):
    """One jurisdiction's own rules."""

    application_fee: Rupees
    copy_fee_per_page: Rupees
    word_limit: WordLimit | None = None  # the 500-word guidance is in the central rules only
    bpl_certificate_required: Flag
    payment_modes: PaymentModes
    filing_channels: FilingChannels


class Rules(_Frozen):
    jurisdiction: Jurisdiction
    act: ActRules
    local: LocalRules


_DATA = files("unseal.rules") / "data"


@cache
def load_rules(jurisdiction: Jurisdiction) -> Rules:
    if jurisdiction not in get_args(Jurisdiction):
        raise ValueError(f"unknown jurisdiction: {jurisdiction!r}")
    act = ActRules.model_validate_json(_DATA.joinpath("rti_act.json").read_text("utf-8"))
    local = LocalRules.model_validate_json(
        _DATA.joinpath(f"{jurisdiction}.json").read_text("utf-8")
    )
    return Rules(jurisdiction=jurisdiction, act=act, local=local)


def sources(rules: Rules) -> dict[str, Source]:
    """Every rule in `rules`, keyed `act.<name>` or `local.<name>`."""
    found: dict[str, Source] = {}
    for prefix, part in (("act", rules.act), ("local", rules.local)):
        for name in type(part).model_fields:
            value = getattr(part, name)
            if isinstance(value, Source):
                found[f"{prefix}.{name}"] = value
    return found


def stale_rules(rules: Rules, today: date) -> list[str]:
    """Rules whose source was last opened more than RECHECK_AFTER_DAYS ago (UI: "recheck")."""
    limit = today - timedelta(days=RECHECK_AFTER_DAYS)
    return [name for name, src in sources(rules).items() if src.checked_on < limit]
