"""What the application and the appeal renderers share: fonts, the Jinja2 environment, dates
written out in the document language, script detection for user text, and the PDF step.

WeasyPrint needs Pango and HarfBuzz (they shape Tamil and Devanagari), so it is imported inside
`html_to_pdf` only: this module still imports on a machine without them.
"""

import re
from collections.abc import Callable, Sequence
from datetime import date
from functools import cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup, escape

from unseal.pdf.labels import Language

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "templates"
FONT_DIR = PACKAGE_DIR / "fonts"

# (CSS family, file stem). Each family has a Regular and a Bold static TrueType file.
FONT_FAMILIES = (
    ("Noto Sans", "NotoSans"),
    ("Noto Sans Tamil", "NotoSansTamil"),
    ("Noto Sans Devanagari", "NotoSansDevanagari"),
)
FONT_WEIGHTS = (("Regular", 400), ("Bold", 700))

_TAMIL = re.compile(r"[஀-௿]")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN = re.compile(r"[A-Za-z]")


def text_language(text: str, default: Language) -> Language:
    """The language of a run of user text by its script; `default` when it has no letters."""
    counts: list[tuple[Language, int]] = [
        ("ta", len(_TAMIL.findall(text))),
        ("hi", len(_DEVANAGARI.findall(text))),
        ("en", len(_LATIN.findall(text))),
    ]
    best_language, best = max(counts, key=lambda pair: pair[1])
    return best_language if best else default


def user_text(document_language: Language) -> Callable[[str], Markup]:
    """The template's `run()`: escape user text, and mark it with its own `lang` when it is not in
    the document language (so the right Noto font shapes it)."""

    def run(text: str) -> Markup:
        language = text_language(text, document_language)
        if language == document_language:
            return escape(text)
        return Markup('<span lang="{}">{}</span>').format(language, text)

    return run


def date_text(day: date, months: Sequence[str]) -> str:
    """`27 October 2026`, with the month name in the document language."""
    return f"{day.day} {months[day.month - 1]} {day.year}"


def font_faces() -> list[dict[str, object]]:
    return [
        {
            "family": family,
            "weight": weight,
            "url": (FONT_DIR / f"{stem}-{style}.ttf").as_uri(),
        }
        for family, stem in FONT_FAMILIES
        for style, weight in FONT_WEIGHTS
    ]


@cache
def environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def html_to_pdf(html: str) -> bytes:
    # Needs Pango and HarfBuzz, so imported only when rendering. WeasyPrint ships no type stubs.
    from weasyprint import HTML  # type: ignore[import-untyped]

    pdf = HTML(string=html, base_url=PACKAGE_DIR.as_uri() + "/").write_pdf()
    if not isinstance(pdf, bytes):
        raise RuntimeError("WeasyPrint returned no PDF bytes")
    return pdf
