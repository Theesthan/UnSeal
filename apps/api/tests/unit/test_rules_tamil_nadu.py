"""Tamil Nadu's own rules (fees, payment modes, filing channels), pinned to the sources they were
read from. The statute lives once in rti_act.json (ADR 0001), so it is not repeated here; these
tests also guard against that copy creeping back in."""

import json
from datetime import date, timedelta
from importlib.resources import files
from urllib.parse import urlparse

import pytest

from unseal.rules.engine import (
    RECHECK_AFTER_DAYS,
    ActRules,
    LocalRules,
    Rules,
    Source,
    load_rules,
    sources,
    stale_rules,
)


@pytest.fixture(scope="module")
def tn() -> Rules:
    return load_rules("tamil_nadu")


def local_sources(rules: Rules) -> dict[str, Source]:
    return {name: src for name, src in sources(rules).items() if name.startswith("local.")}


def test_tamil_nadu_rules_load(tn: Rules) -> None:
    assert tn.jurisdiction == "tamil_nadu"


def test_tamil_nadu_fees(tn: Rules) -> None:
    assert tn.local.application_fee.rupees == 10
    assert tn.local.copy_fee_per_page.rupees == 2
    # The quotes must name the same amounts, so a value edit without its source fails.
    assert "rupees ten" in tn.local.application_fee.quote
    assert "rupees two" in tn.local.copy_fee_per_page.quote


def test_no_word_limit(tn: Rules) -> None:
    # No Tamil Nadu rule limits the length of an application; the 500-word guidance is central.
    assert tn.local.word_limit is None


def test_bpl_applicants_attach_a_certificate(tn: Rules) -> None:
    assert tn.local.bpl_certificate_required.applies is True
    # The Tamil Nadu fee rules are silent on BPL; the note must say where the proof rule comes from.
    assert tn.local.bpl_certificate_required.note


def test_payment_modes_are_exactly_rule_3a(tn: Rules) -> None:
    modes = set(tn.local.payment_modes.modes)
    assert modes == {
        "cash",
        "court_fee_stamp",
        "postal_money_order",
        "demand_draft",
        "bankers_cheque",
    }
    # Differences from the central default that a user would otherwise get wrong.
    assert "indian_postal_order" not in modes
    assert "electronic" not in modes


def test_payment_modes_match_their_quote(tn: Rules) -> None:
    quote = tn.local.payment_modes.quote.lower()
    wording = {
        "cash": "cash",
        "court_fee_stamp": "court fee stamp",
        "postal_money_order": "postal money order",
        "demand_draft": "demand draft",
        "bankers_cheque": "bankers cheque",
    }
    assert set(wording) == set(tn.local.payment_modes.modes)
    for mode, words in wording.items():
        assert words in quote, mode
    assert "postal order" not in quote.replace("postal money order", "")


def test_filing_channels(tn: Rules) -> None:
    assert set(tn.local.filing_channels.channels) == {"rti_online", "post", "in_person"}


def test_tamil_nadu_rules_are_not_under_challenge(tn: Rules) -> None:
    assert [name for name, src in local_sources(tn).items() if src.under_challenge] == []


def test_every_tamil_nadu_rule_has_primary_provenance(tn: Rules) -> None:
    found = local_sources(tn)
    # word_limit is null for Tamil Nadu, so five rules carry a source.
    assert sorted(found) == [
        "local.application_fee",
        "local.bpl_certificate_required",
        "local.copy_fee_per_page",
        "local.filing_channels",
        "local.payment_modes",
    ]
    for name, src in found.items():
        host = urlparse(str(src.source_url)).hostname or ""
        assert src.source_url.scheme == "https", name
        # Primary sources only: official Indian government hosts. Explainers are leads, not sources.
        assert host.endswith((".gov.in", ".nic.in")), f"{name}: {host}"
        assert src.quote.strip(), name
        assert src.basis.strip(), name
        assert src.checked_on <= date.today(), name
        assert chr(0x2014) not in src.quote + src.basis + (src.note or ""), name  # no em dash


def test_statute_is_not_duplicated_in_the_tamil_nadu_file(tn: Rules) -> None:
    # The Act applies to every jurisdiction, so the statute part is the same content as central.
    assert tn.act == load_rules("central").act
    raw = json.loads(
        files("unseal.rules").joinpath("data/tamil_nadu.json").read_text(encoding="utf-8")
    )
    assert set(raw) <= set(LocalRules.model_fields)
    assert not set(raw) & set(ActRules.model_fields)


def test_tamil_nadu_rules_join_the_recheck_warning(tn: Rules) -> None:
    found = local_sources(tn)
    newest = max(src.checked_on for src in found.values())
    oldest = min(src.checked_on for src in found.values())
    # The statute rules carry their own dates, so look at the Tamil Nadu rules only.
    on_boundary = stale_rules(tn, today=oldest + timedelta(days=RECHECK_AFTER_DAYS))
    assert [name for name in on_boundary if name.startswith("local.")] == []
    stale = stale_rules(tn, today=newest + timedelta(days=RECHECK_AFTER_DAYS + 1))
    assert set(found) <= set(stale)
