"""Application PDF renderer: Jinja2 builds the HTML, WeasyPrint turns it into a PDF.

`render_application_html` is pure and runs anywhere. `render_application_pdf` needs WeasyPrint's
system libraries (Pango and HarfBuzz do the Tamil and Devanagari shaping), so WeasyPrint is
imported inside that function: this module still imports on a machine without them.

The fee shown comes from `load_rules(doc.jurisdiction)`, never from a literal. The page has no
image, emblem or seal and nothing that claims official status; every page ends with the
"Prepared with UnSeal. Not legal advice." footer.
"""

import re
from functools import cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup, escape

from unseal.pdf.labels import Labels, Language, labels_for
from unseal.pdf.models import ApplicationDocument
from unseal.rules.engine import Rules, load_rules

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "templates"
FONT_DIR = PACKAGE_DIR / "fonts"
TEMPLATE_NAME = "application.html.j2"

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


def _font_faces() -> list[dict[str, object]]:
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
def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def _date_text(doc: ApplicationDocument, labels: Labels) -> str:
    day = doc.prepared_on
    return f"{day.day} {labels.months[day.month - 1]} {day.year}"


def _payment_text(doc: ApplicationDocument, labels: Labels) -> str | None:
    """The payment mode in the document language; text outside the known codes is shown as given."""
    if doc.payment_mode is None or not doc.payment_mode.strip():
        return None
    return labels.payment_modes.get(doc.payment_mode, doc.payment_mode)


def _context(doc: ApplicationDocument, rules: Rules) -> dict[str, object]:
    labels = labels_for(doc.language)
    exempt = doc.bpl and rules.act.bpl_fee_exempt.applies
    amount = labels.fee_amount.format(rupees=rules.local.application_fee.rupees)

    def run(text: str) -> Markup:
        """Escape user text; mark it with its own `lang` when it is not in the document language."""
        language = text_language(text, doc.language)
        if language == doc.language:
            return escape(text)
        return Markup('<span lang="{}">{}</span>').format(language, text)

    return {
        "doc": doc,
        "lang": doc.language,
        "l": labels,
        "run": run,
        "fee_text": labels.fee_nil if exempt else amount,
        "show_certificate_note": exempt and rules.local.bpl_certificate_required.applies,
        "payment_text": None if exempt else _payment_text(doc, labels),
        "date_text": _date_text(doc, labels),
        "font_faces": _font_faces(),
    }


def render_application_html(doc: ApplicationDocument) -> str:
    rules = load_rules(doc.jurisdiction)
    template = _environment().get_template(TEMPLATE_NAME)
    return template.render(_context(doc, rules))


def render_application_pdf(doc: ApplicationDocument) -> bytes:
    # Needs Pango and HarfBuzz, so imported only when rendering. WeasyPrint ships no type stubs.
    from weasyprint import HTML  # type: ignore[import-untyped]

    html = render_application_html(doc)
    pdf = HTML(string=html, base_url=PACKAGE_DIR.as_uri() + "/").write_pdf()
    if not isinstance(pdf, bytes):
        raise RuntimeError("WeasyPrint returned no PDF bytes")
    return pdf
