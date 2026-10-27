"""Fixed Tamil and Hindi terms for RTI concepts (glossary.json), used two ways:

- prompts get `glossary_block(language)` so the model uses the right term;
- the language eval counts `term_errors` (known-wrong variants) and `missed_terms` (a concept the
  case names in English whose preferred term is absent from the output).

`match` holds stems, not whole words: Tamil adds case endings (நகல் -> நகலை, நகல்கள்) and Hindi
plurals change the ending (प्रति -> प्रतियाँ). Hindi nuktas are ignored when matching (फ़ाइल = फाइल).
"""

import unicodedata
from functools import cache
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

Language = Literal["ta", "hi"]

_NUKTA = "़"


class LocalTerm(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    term: str
    match: tuple[str, ...] = Field(min_length=1)
    avoid: tuple[str, ...] = ()
    source: str = Field(min_length=1)  # where the term was checked (statute, glossary, order)
    confidence: Literal["high", "medium", "low"]  # low: a native reviewer checks it first


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    concept: str
    en: tuple[str, ...] = Field(min_length=1)
    ta: LocalTerm
    hi: LocalTerm

    def local(self, language: Language) -> LocalTerm:
        return self.ta if language == "ta" else self.hi


@cache
def load_glossary() -> tuple[Entry, ...]:
    raw = (files("unseal.llm") / "glossary.json").read_bytes()
    return tuple(TypeAdapter(list[Entry]).validate_json(raw))


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text).replace(_NUKTA, "")
    return " ".join(unicodedata.normalize("NFC", decomposed).split())


def glossary_block(language: Language) -> str:
    """One line per concept: `- certified copy: <term>`."""
    return "\n".join(f"- {e.concept}: {e.local(language).term}" for e in load_glossary())


def term_errors(text: str, language: Language) -> list[str]:
    """Known-wrong variants found in `text`, as `concept: variant`."""
    found = _norm(text)
    return [
        f"{e.concept}: {bad}"
        for e in load_glossary()
        for bad in e.local(language).avoid
        if _norm(bad) in found
    ]


def missed_terms(text: str, language: Language, source: str) -> list[str]:
    """Concepts named in the English `source` whose preferred term is absent from `text`."""
    wanted, found = source.lower(), _norm(text)
    return [
        e.concept
        for e in load_glossary()
        if any(phrase in wanted for phrase in e.en)
        and not any(_norm(stem) in found for stem in e.local(language).match)
    ]
