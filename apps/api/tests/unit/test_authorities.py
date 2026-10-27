"""The curated authority list (PRD FR-4): who an RTI application is addressed to.

Every entry carries the official page its PIO and address were read from, plus a verbatim quote.
These tests pin the shape of that data, the model's guards, and the lookup ranking."""

import unicodedata
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlparse

import pytest
from pydantic import ValidationError

from unseal.rules.authorities import (
    ALLOWED_SOURCE_HOST_SUFFIXES,
    RTI_ONLINE_HOSTS,
    Authority,
    AuthorityList,
    load_authorities,
    lookup_authority,
    normalise_text,
    stale_authorities,
)
from unseal.rules.engine import RECHECK_AFTER_DAYS


def ids(query: str, jurisdiction: str | None = None, limit: int = 5) -> list[str]:
    return [a.id for a in lookup_authority(query, jurisdiction, limit)]


def host(url: object) -> str:
    return urlparse(str(url)).hostname or ""


@pytest.fixture
def valid() -> dict[str, Any]:
    """A valid entry as JSON-ready data, taken from the real list (a fresh copy per test)."""
    return load_authorities()[0].model_dump(mode="json")


# ---------------------------------------------------------------- the data file


def test_file_loads_and_is_cached() -> None:
    authorities = load_authorities()
    assert len(authorities) >= 12
    assert all(isinstance(a, Authority) for a in authorities)
    assert load_authorities() is authorities


def test_ids_are_unique() -> None:
    found = [a.id for a in load_authorities()]
    assert len(found) == len(set(found))


def test_both_jurisdictions_are_present() -> None:
    assert {a.jurisdiction for a in load_authorities()} == {"central", "tamil_nadu"}


def test_every_authority_has_official_provenance() -> None:
    for a in load_authorities():
        assert urlparse(str(a.source_url)).scheme == "https", a.id
        assert host(a.source_url).endswith(ALLOWED_SOURCE_HOST_SUFFIXES), a.id
        assert a.quote.strip(), a.id
        assert a.pio_designation.strip(), a.id
        assert a.pio_address.strip(), a.id
        assert isinstance(a.checked_on, date), a.id


def test_designation_and_address_sit_inside_the_quote() -> None:
    """An address or designation that drifted from its quote is a transcription error."""

    def fold(text: str) -> str:
        return "".join(ch for ch in text.casefold() if ch.isascii() and ch.isalnum())

    for a in load_authorities():
        assert fold(a.pio_designation) in fold(a.quote), a.id
        assert fold(a.pio_address) in fold(a.quote), a.id


def test_aliases_are_not_shared_between_authorities() -> None:
    owner: dict[str, str] = {}
    for a in load_authorities():
        for alias in a.aliases:
            assert alias not in owner, f"{alias!r}: {owner[alias]} and {a.id}"
            owner[alias] = a.id


def test_rti_online_claims_cite_an_rti_online_page() -> None:
    claimed = [a for a in load_authorities() if a.rti_online is not None]
    assert claimed
    for a in claimed:
        assert a.rti_online_source is not None, a.id
        assert host(a.rti_online_source) in RTI_ONLINE_HOSTS, a.id


def test_native_names_cite_an_official_page() -> None:
    named = [a for a in load_authorities() if a.name_ta or a.name_hi]
    assert named
    for a in named:
        assert a.native_names_source is not None, a.id
        assert host(a.native_names_source).endswith(ALLOWED_SOURCE_HOST_SUFFIXES), a.id


# ------------------------------------------------------------------ the model


def test_valid_entry_round_trips(valid: dict[str, Any]) -> None:
    assert Authority.model_validate(valid) == load_authorities()[0]


def test_entries_are_frozen() -> None:
    with pytest.raises(ValidationError):
        load_authorities()[0].name = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "Not_Kebab"),
        ("id", ""),
        ("jurisdiction", "delhi"),
        ("name", ""),
        ("source_url", "https://example.com/rti"),
        ("source_url", "https://rti.gov.in.evil.example/page"),
        ("source_url", "http://www.cbse.gov.in/rti.html"),
        ("quote", ""),
        ("pio_designation", ""),
        ("pio_address", ""),
        ("aliases", []),
        ("aliases", ["CBSE"]),
        ("aliases", ["two  spaces"]),
        ("aliases", [""]),
        ("aliases", ["cbse", "cbse"]),
        ("rti_online", True),
        ("rti_online_source", "https://example.com/list"),
        ("name_ta", "English only"),
        ("name_hi", "Tamil நாடு"),
        ("pio_designation", "A designation the quote does not contain"),
        ("pio_address", "An address the quote does not contain"),
        ("unknown_field", "x"),
    ],
)
def test_invalid_entries_are_rejected(valid: dict[str, Any], field: str, value: object) -> None:
    broken = {**valid, field: value}
    if field == "rti_online":
        broken["rti_online_source"] = None
    with pytest.raises(ValidationError):
        Authority.model_validate(broken)


def test_native_name_without_a_source_is_rejected(valid: dict[str, Any]) -> None:
    broken = {**valid, "name_ta": "தமிழ்", "native_names_source": None}
    with pytest.raises(ValidationError):
        Authority.model_validate(broken)


def test_rti_online_flag_without_a_source_is_rejected(valid: dict[str, Any]) -> None:
    broken = {**valid, "rti_online": True, "rti_online_source": None}
    with pytest.raises(ValidationError):
        Authority.model_validate(broken)


def test_native_names_need_the_right_script(valid: dict[str, Any]) -> None:
    source = "https://dge.tn.gov.in/rti.html"
    good = {**valid, "name_ta": "தமிழ்", "name_hi": "हिन्दी", "native_names_source": source}
    assert Authority.model_validate(good).name_hi == "हिन्दी"
    with pytest.raises(ValidationError):
        Authority.model_validate({**good, "name_hi": "தமிழ்"})


def test_list_rejects_duplicate_ids_and_an_empty_list(valid: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        AuthorityList.model_validate({"authorities": [valid, valid]})
    with pytest.raises(ValidationError):
        AuthorityList.model_validate({"authorities": []})
    with pytest.raises(ValidationError):
        AuthorityList.model_validate({"authorities": [valid], "extra": 1})


# ---------------------------------------------------------------- normalisation


def test_normalise_text_folds_case_space_punctuation_and_unicode_form() -> None:
    assert normalise_text("  Madras   UNIVERSITY, Chepauk. ") == "madras university chepauk"
    assert normalise_text("Employees' Provident Fund") == "employees provident fund"
    decomposed = "கொ"
    assert normalise_text(decomposed) == "கொ"
    assert normalise_text("   ") == ""


# ----------------------------------------------------------------------- lookup


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("cbse", "cbse-regional-office-chennai"),
        ("pf withdrawal epfo", "epfo-regional-office-chennai"),
        ("passport", "passport-regional-office-chennai"),
        ("ration card", "civil-supplies-consumer-protection"),
        ("madras university exam", "university-of-madras"),
        ("road corporation chennai", "greater-chennai-corporation"),
        ("aadhaar", "uidai-regional-office-bengaluru"),
        ("sslc", "directorate-of-government-examinations"),
        ("metro water", "chennai-metro-water-board"),
        ("income tax refund", "income-tax-department-chennai"),
        ("iit madras", "iit-madras"),
        ("railway", "southern-railway-headquarters"),
        ("tnpsc group 4", "tamil-nadu-public-service-commission"),
        ("collector", "chennai-district-collectorate"),
    ],
)
def test_lookup_returns_the_expected_authority_first(query: str, expected: str) -> None:
    assert ids(query)[0] == expected


def test_lookup_is_case_and_whitespace_insensitive() -> None:
    assert ids("  CBSE  ") == ids("cbse")
    assert ids("Madras    University")[0] == "university-of-madras"
    assert ids("RATION\tCARD\n")[0] == "civil-supplies-consumer-protection"


def test_exact_alias_beats_alias_phrase_beats_name_words() -> None:
    ordered = ids("chennai corporation", limit=20)
    assert ordered[0] == "greater-chennai-corporation"  # exact alias
    assert "chennai-metro-water-board" in ordered  # matched only by a word of its name
    assert ids("university")[0] == "university-of-madras"  # a word of the name
    both = ids("madras", limit=20)  # only alias phrases match: each of the two names has one
    assert set(both) == {"iit-madras", "university-of-madras"}


def test_every_authority_is_found_by_its_own_name() -> None:
    for a in load_authorities():
        assert ids(a.name)[0] == a.id, a.name


def test_jurisdiction_filter() -> None:
    assert ids("madras", "central")[0] == "iit-madras"
    assert ids("madras", "tamil_nadu")[0] == "university-of-madras"
    for jurisdiction in ("central", "tamil_nadu"):
        found = lookup_authority("chennai", jurisdiction, limit=50)
        assert found
        assert {a.jurisdiction for a in found} == {jurisdiction}
    assert ids("cbse", "tamil_nadu") == []


def test_unknown_jurisdiction_and_bad_limit_are_errors() -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        lookup_authority("cbse", "delhi")
    with pytest.raises(ValueError, match="limit"):
        lookup_authority("cbse", limit=0)


@pytest.mark.parametrize("query", ["", "   ", "\n\t", " , . "])
def test_empty_query_returns_nothing(query: str) -> None:
    assert lookup_authority(query) == []


def test_unknown_query_returns_nothing() -> None:
    assert lookup_authority("zzqx plugh") == []
    assert lookup_authority("zz", "central") == []


def test_limit_caps_the_results() -> None:
    assert len(lookup_authority("chennai", limit=2)) == 2
    assert len(lookup_authority("chennai")) <= 5
    assert len(lookup_authority("chennai", limit=50)) > 5


def test_tamil_name_queries_match_the_official_native_name() -> None:
    dge = next(a for a in load_authorities() if a.id == "directorate-of-government-examinations")
    assert dge.name_ta is not None
    assert ids(dge.name_ta)[0] == dge.id
    assert ids(unicodedata.normalize("NFD", dge.name_ta))[0] == dge.id
    assert ids("இயக்ககம் சான்றிதழ்")[0] == dge.id  # a word of the name inside a longer query
    assert ids("தமிழ்நாடு அரசுப் பணியாளர் தேர்வாணையம்")[0] == "tamil-nadu-public-service-commission"
    assert ids("குடிநீர் வழங்கல்")[0] == "chennai-metro-water-board"
    assert ids("தேர்வுகள்", "central") == []


def test_native_names_match_even_when_no_english_word_does() -> None:
    assert ids("இயக்ககம்") == ["directorate-of-government-examinations"]
    assert ids("வாரியம்") == ["chennai-metro-water-board"]


# ---------------------------------------------------------------- recheck rule


def test_stale_authorities_follow_the_recheck_window() -> None:
    authorities = load_authorities()
    oldest = min(a.checked_on for a in authorities)
    assert stale_authorities(max(a.checked_on for a in authorities)) == []
    assert stale_authorities(oldest + timedelta(days=RECHECK_AFTER_DAYS)) == []
    flagged = stale_authorities(oldest + timedelta(days=RECHECK_AFTER_DAYS + 1))
    assert flagged
    assert all(a.id in flagged for a in authorities if a.checked_on == oldest)
    assert set(stale_authorities(date(2100, 1, 1))) == {a.id for a in authorities}
