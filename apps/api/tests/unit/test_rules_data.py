"""The rules data is the only home for legal values. These tests pin the researched values,
so an accidental JSON edit fails loudly, and enforce that every rule carries its provenance."""

from datetime import date, timedelta
from urllib.parse import urlparse

import pytest
from pydantic import ValidationError

from unseal.rules.engine import (
    RECHECK_AFTER_DAYS,
    ActRules,
    Rules,
    Source,
    load_rules,
    stale_rules,
)


@pytest.fixture(scope="module")
def central() -> Rules:
    return load_rules("central")


def all_sources(rules: Rules) -> dict[str, Source]:
    found: dict[str, Source] = {}
    for part_name in ("act", "local"):
        part = getattr(rules, part_name)
        for field_name in type(part).model_fields:
            value = getattr(part, field_name)
            if isinstance(value, Source):
                found[f"{part_name}.{field_name}"] = value
    return found


def test_statutory_deadlines(central: Rules) -> None:
    act = central.act
    assert act.pio_reply.days == 30
    assert act.apio_extra.days == 5
    assert act.third_party_reply.days == 40
    assert act.life_liberty_reply.hours == 48
    assert act.transfer.days == 5
    assert act.first_appeal.days == 30
    assert act.first_appeal.late_allowed is True
    assert (act.faa_decision.days, act.faa_decision.max_days) == (30, 45)
    assert act.second_appeal.days == 90
    assert act.second_appeal.late_allowed is True


def test_statutory_flags(central: Rules) -> None:
    act = central.act
    assert act.deemed_refusal.applies is True
    assert act.bpl_fee_exempt.applies is True
    assert act.no_reason_needed.applies is True
    assert act.personal_information.applies is True


def test_only_personal_information_is_under_challenge(central: Rules) -> None:
    flagged = [name for name, src in all_sources(central).items() if src.under_challenge]
    assert flagged == ["act.personal_information"]
    assert central.act.personal_information.note  # says which case, so the UI can cite it


def test_languages(central: Rules) -> None:
    assert central.act.languages.codes == ("en", "hi")
    assert central.act.languages.plus_area_official_language is True


def test_central_fees_and_length(central: Rules) -> None:
    local = central.local
    assert central.jurisdiction == "central"
    assert local.application_fee.rupees == 10
    assert local.copy_fee_per_page.rupees == 2
    assert local.word_limit is not None
    assert local.word_limit.words == 500
    assert local.word_limit.blocks_filing is False
    assert local.bpl_certificate_required.applies is True
    assert set(local.payment_modes.modes) == {
        "cash",
        "demand_draft",
        "bankers_cheque",
        "indian_postal_order",
        "electronic",
    }
    assert set(local.filing_channels.channels) == {"rti_online", "post", "in_person"}


def test_every_rule_has_primary_provenance(central: Rules) -> None:
    sources = all_sources(central)
    assert len(sources) >= 17
    for name, src in sources.items():
        host = urlparse(str(src.source_url)).hostname or ""
        assert src.source_url.scheme == "https", name
        # Primary sources only: official Indian government hosts. Explainers are leads, not sources.
        assert host.endswith((".gov.in", ".nic.in")), f"{name}: {host}"
        assert src.quote.strip(), name
        assert src.basis.strip(), name
        assert src.checked_on <= date.today(), name


def test_unknown_keys_are_rejected(central: Rules) -> None:
    data = central.act.model_dump(mode="json")
    data["pio_reply_dayz"] = data["pio_reply"]
    with pytest.raises(ValidationError):
        ActRules.model_validate(data)


def test_rules_are_immutable(central: Rules) -> None:
    with pytest.raises(ValidationError):
        central.act.pio_reply.days = 1  # type: ignore[misc]


def test_unknown_jurisdiction_fails() -> None:
    with pytest.raises(ValueError):
        load_rules("kerala")  # type: ignore[arg-type]


def test_stale_rules_boundary(central: Rules) -> None:
    newest = max(src.checked_on for src in all_sources(central).values())
    oldest = min(src.checked_on for src in all_sources(central).values())
    assert stale_rules(central, today=oldest + timedelta(days=RECHECK_AFTER_DAYS)) == []
    stale = stale_rules(central, today=newest + timedelta(days=RECHECK_AFTER_DAYS + 1))
    assert sorted(stale) == sorted(all_sources(central))
