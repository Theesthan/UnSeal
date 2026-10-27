"""Shared helpers for the second appeal tests (no tests of its own).

The golden cases are named <format>-<language>: cic-en, cic-hi, cic-ta, tnsic-en, tnsic-ta.
"""

import json
import re
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal

from unseal.llm.glossary import load_glossary
from unseal.pdf.models import SecondAppealDocument
from unseal.rules.engine import Rules, load_rules

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "pdf"
CASES: dict[str, dict[str, object]] = json.loads(
    (GOLDEN / "second-appeal-cases.json").read_text("utf-8")
)
FOOTER_EN = "Prepared with UnSeal. Not legal advice."
FOOTER_LOCAL = {
    "hi": "UnSeal द्वारा तैयार किया गया। यह कानूनी सलाह नहीं है।",
    "ta": "UnSeal மூலம் தயாரிக்கப்பட்டது. இது சட்ட ஆலோசனை அல்ல.",
}
EM_DASH = chr(0x2014)  # built from its code point so this file has none itself
SOURCES = (
    "second_appeal.py",
    "second_appeal_labels.py",
    "cic_labels.py",
    "tnsic_labels.py",
    "templates/second_appeal_cic.html.j2",
    "templates/second_appeal_tnsic.html.j2",
    "templates/_second_appeal_style.html.j2",
    "templates/_second_appeal_parts.html.j2",
)
# The sections the real rules carry today; a test swaps every one of them for another number.
REAL_SECTIONS = ("19(3)", "19(1)", "6(1)", "6(3)", "7(2)", "19(6)")
FAKE_BASES = {
    "second_appeal": "RTI Act 2005, s. 93(3) and proviso",
    "first_appeal": "RTI Act 2005, s. 91(1) and proviso",
    "languages": "RTI Act 2005, s. 84(1)",
    "transfer": "RTI Act 2005, s. 85(3), proviso",
    "deemed_refusal": "RTI Act 2005, s. 78(2)",
    "faa_decision": "RTI Act 2005, s. 99(6)",
}
# No fake contains a real one as a substring ("66(1)" would contain "6(1)").
FAKE_SECTIONS = ("93(3)", "91(1)", "84(1)", "85(3)", "78(2)", "99(6)")


def case(name: str, **changes: object) -> SecondAppealDocument:
    return SecondAppealDocument.model_validate({**CASES[name], **changes})


INLINE = {"time", "span", "strong", "em", "b", "i", "a"}


class Page(HTMLParser):
    """Visible text (no CSS, no <title>), <li> texts, (dt, dd) pairs and table rows.

    Block tags separate words; inline tags (a <time> inside a sentence) do not.
    """

    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.items: list[str] = []
        self.rows: list[tuple[str, str]] = []
        self.cells: list[list[str]] = []
        self._skip = 0
        self._open: dict[str, list[str]] = {}
        self._dt = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._separate(tag)
        if tag in {"style", "title"}:
            self._skip += 1
        elif tag == "tr":
            self.cells.append([])
        elif tag in {"li", "dt", "dd", "td", "th"}:
            self._open[tag] = []

    def _separate(self, tag: str) -> None:
        if tag not in INLINE and not self._skip:
            self.text.append(" ")
            for parts in self._open.values():
                parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        self._separate(tag)
        if tag in {"style", "title"}:
            self._skip -= 1
            return
        if tag not in self._open:
            return
        text = " ".join("".join(self._open.pop(tag)).split())
        if tag == "li":
            self.items.append(text)
        elif tag == "dt":
            self._dt = text
        elif tag == "dd":
            self.rows.append((self._dt, text))
        else:
            if not self.cells:  # a chunk cut after its <tr>
                self.cells.append([])
            self.cells[-1].append(text)

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        self.text.append(data)
        for parts in self._open.values():
            parts.append(data)


def parse(html: str) -> Page:
    page = Page()
    page.feed(html)
    return page


def visible(html: str) -> str:
    return " ".join("".join(parse(html).text).split())


def options(html: str) -> list[tuple[str, bool]]:
    """Every tick box in `html` in order: (its label, whether it is ticked)."""
    found = re.findall(
        r'<span class="option( ticked)?"><span class="box"[^>]*>X?</span>\s*(.*?)</span>',
        html,
        re.S,
    )
    return [(" ".join(label.split()), bool(ticked)) for ticked, label in found]


def term(concept: str, language: Literal["hi", "ta"]) -> str:
    (entry,) = [e for e in load_glossary() if e.concept == concept]
    return entry.local(language).term


def rules_with(
    *, fmt: str | None = None, enclosures: tuple[str, ...] | None = None, **bases: str
) -> Callable[[str], Rules]:
    """A stand-in for load_rules: other act `basis` texts, or another second appeal format."""

    def fake(jurisdiction: str) -> Rules:
        real = load_rules(jurisdiction)  # type: ignore[arg-type]
        act = real.act.model_copy(
            update={
                name: getattr(real.act, name).model_copy(update={"basis": basis})
                for name, basis in bases.items()
            }
        )
        form = real.local.second_appeal_format
        changes: dict[str, object] = {}
        if fmt is not None:
            changes["format"] = fmt
        if enclosures is not None:
            changes["enclosures"] = enclosures
        local = real.local.model_copy(
            update={"second_appeal_format": form.model_copy(update=changes)}
        )
        return real.model_copy(update={"act": act, "local": local})

    return fake
