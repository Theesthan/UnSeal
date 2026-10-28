"""Authority routing (PRD FR-4): the curated list of public authorities and their PIOs.

The data lives in rules/data/authorities.json, never in code. Each entry carries the official page
its PIO and address were read from, the day someone opened it and a verbatim quote (the same
provenance pattern as engine.Source, ADR 0001). `lookup_authority` only ranks candidates for the
user to confirm: it never picks for them, and it never invents or repairs an address.
"""

import re
import string
import unicodedata
from datetime import date, timedelta
from functools import cache
from importlib.resources import files
from typing import Annotated, Self, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

from unseal.rules.engine import RECHECK_AFTER_DAYS, Jurisdiction

# A source must be an official page: the same hosts the rules data accepts, plus university hosts.
ALLOWED_SOURCE_HOST_SUFFIXES = (".gov.in", ".nic.in", ".ac.in", ".edu.in")
RTI_ONLINE_HOSTS = ("rtionline.gov.in", "rtionline.tn.gov.in")

_NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_TAMIL = re.compile(r"[஀-௿]")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_SEPARATORS = re.compile(r"[\s" + re.escape(string.punctuation) + "‐-―‘’“”" + r"]+")
_STOPWORDS = frozenset({"the", "and", "for", "office"})
_MIN_WORD_LENGTH = 3
_DATA = files("unseal.rules") / "data"


def normalise_text(text: str) -> str:
    """Lower-case, NFC-normalise and collapse spaces and punctuation: the form lookups compare."""
    folded = unicodedata.normalize("NFC", text).casefold()
    return _SEPARATORS.sub(" ", folded).strip()


def _fold(text: str) -> str:
    """Letters and digits only, for checking that a field sits inside the quote it came from."""
    return "".join(ch for ch in text.casefold() if ch.isascii() and ch.isalnum())


def _host(url: HttpUrl) -> str:
    return url.host or ""


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Authority(_Frozen):
    """One public authority and the PIO an application to it is addressed to.

    `quote` is verbatim from `source_url` (several pieces may be joined with ' ... '), and
    `checked_on` is the day someone opened that page. `pio_designation` and `pio_address` are as
    published; the native names are given only where an official page gives them.
    """

    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    jurisdiction: Jurisdiction
    name: _NonBlank
    name_ta: _NonBlank | None = None
    name_hi: _NonBlank | None = None
    native_names_source: HttpUrl | None = None
    aliases: tuple[str, ...] = Field(min_length=1)
    pio_designation: _NonBlank
    pio_address: _NonBlank
    rti_online: bool | None = None  # None: not checked
    rti_online_source: HttpUrl | None = None
    source_url: HttpUrl
    checked_on: date
    quote: _NonBlank
    note: str | None = None

    @field_validator("source_url", "native_names_source")
    @classmethod
    def _official_https_page(cls, url: HttpUrl | None) -> HttpUrl | None:
        if url is not None and (
            url.scheme != "https" or not _host(url).endswith(ALLOWED_SOURCE_HOST_SUFFIXES)
        ):
            raise ValueError(f"not an official https page: {url}")
        return url

    @field_validator("rti_online_source")
    @classmethod
    def _rti_online_page(cls, url: HttpUrl | None) -> HttpUrl | None:
        if url is not None and (url.scheme != "https" or _host(url) not in RTI_ONLINE_HOSTS):
            raise ValueError(f"not an RTI Online page: {url}")
        return url

    @field_validator("aliases")
    @classmethod
    def _aliases_are_normalised(cls, aliases: tuple[str, ...]) -> tuple[str, ...]:
        for alias in aliases:
            if not alias or alias != normalise_text(alias):
                raise ValueError(f"alias must be non-empty and normalised: {alias!r}")
        if len(set(aliases)) != len(aliases):
            raise ValueError("duplicate alias")
        return aliases

    @field_validator("name_ta")
    @classmethod
    def _tamil(cls, name: str | None) -> str | None:
        if name is not None and not _TAMIL.search(name):
            raise ValueError("name_ta has no Tamil characters")
        return name

    @field_validator("name_hi")
    @classmethod
    def _hindi(cls, name: str | None) -> str | None:
        if name is not None and not _DEVANAGARI.search(name):
            raise ValueError("name_hi has no Devanagari characters")
        return name

    @model_validator(mode="after")
    def _claims_have_sources(self) -> Self:
        if (self.rti_online is None) != (self.rti_online_source is None):
            raise ValueError("rti_online and rti_online_source go together")
        if bool(self.name_ta or self.name_hi) != (self.native_names_source is not None):
            raise ValueError("native names and native_names_source go together")
        return self

    @model_validator(mode="after")
    def _fields_come_from_the_quote(self) -> Self:
        quote = _fold(self.quote)
        if _fold(self.pio_designation) not in quote or _fold(self.pio_address) not in quote:
            raise ValueError(f"{self.id}: designation and address must appear in the quote")
        return self


class AuthorityList(_Frozen):
    authorities: tuple[Authority, ...] = Field(min_length=1)

    @field_validator("authorities")
    @classmethod
    def _unique_ids(cls, authorities: tuple[Authority, ...]) -> tuple[Authority, ...]:
        found = [a.id for a in authorities]
        if len(set(found)) != len(found):
            raise ValueError("duplicate authority id")
        return authorities


@cache
def load_authorities() -> tuple[Authority, ...]:
    raw = _DATA.joinpath("authorities.json").read_text("utf-8")
    return AuthorityList.model_validate_json(raw).authorities


def stale_authorities(today: date) -> list[str]:
    """Ids whose source was last opened more than RECHECK_AFTER_DAYS ago (UI: "recheck")."""
    limit = today - timedelta(days=RECHECK_AFTER_DAYS)
    return [a.id for a in load_authorities() if a.checked_on < limit]


def _has_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _words(text: str) -> set[str]:
    return {w for w in text.split() if len(w) >= _MIN_WORD_LENGTH and w not in _STOPWORDS}


def _native_score(authority: Authority, query: str) -> int:
    """How much of the query an official Tamil or Hindi name explains (0: not at all)."""
    best = 0
    for native in (authority.name_ta, authority.name_hi):
        if native is None:
            continue
        name = normalise_text(native)
        if query in name or name in query:
            best = max(best, len(query))
            continue
        matched = [w for w in query.split() if not w.isascii() and len(w) >= 3 and w in name]
        best = max(best, sum(len(w) for w in matched))
    return best


def _rank(authority: Authority, query: str) -> tuple[int, int] | None:
    """Sort key, best first: exact alias, alias in the query, words of the name, native name."""
    if query in authority.aliases:
        return (0, 0)
    hits = [a for a in authority.aliases if _has_phrase(query, a) or _has_phrase(a, query)]
    if hits:
        return (1, -sum(len(a) for a in hits))
    overlap = len(_words(query) & _words(normalise_text(authority.name)))
    if overlap:
        return (2, -overlap)
    native = _native_score(authority, query)
    return (3, -native) if native else None


def lookup_authority(
    query: str, jurisdiction: str | None = None, limit: int = 5
) -> list[Authority]:
    """Candidates for the user to confirm, best first; an empty or unknown query gives none."""
    if jurisdiction is not None and jurisdiction not in get_args(Jurisdiction):
        raise ValueError(f"unknown jurisdiction: {jurisdiction!r}")
    if limit < 1:
        raise ValueError(f"limit must be at least 1, got {limit}")
    text = normalise_text(query)
    if not text:
        return []
    ranked = [
        (key, authority)
        for authority in load_authorities()
        if jurisdiction in (None, authority.jurisdiction)
        if (key := _rank(authority, text)) is not None
    ]
    ranked.sort(key=lambda pair: pair[0])  # stable: ties keep the file order
    return [authority for _, authority in ranked[:limit]]
