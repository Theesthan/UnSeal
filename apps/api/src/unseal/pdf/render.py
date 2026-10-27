"""Application PDF renderer: Jinja2 builds the HTML, WeasyPrint turns it into a PDF.

`render_application_html` is pure and runs anywhere. `render_application_pdf` needs WeasyPrint's
system libraries (Pango and HarfBuzz do the Tamil and Devanagari shaping), so WeasyPrint is
imported inside that step (`common.html_to_pdf`): this module still imports on a machine without
them.

The fee shown comes from `load_rules(doc.jurisdiction)`, never from a literal. The page has no
image, emblem or seal and nothing that claims official status; every page ends with the
"Prepared with UnSeal. Not legal advice." footer.
"""

from unseal.pdf.common import date_text, environment, font_faces, html_to_pdf, user_text
from unseal.pdf.common import text_language as text_language  # re-exported, used to live here
from unseal.pdf.labels import Labels, labels_for
from unseal.pdf.models import ApplicationDocument
from unseal.rules.engine import Rules, load_rules

TEMPLATE_NAME = "application.html.j2"


def _payment_text(doc: ApplicationDocument, labels: Labels) -> str | None:
    """The payment mode in the document language; text outside the known codes is shown as given."""
    if doc.payment_mode is None or not doc.payment_mode.strip():
        return None
    return labels.payment_modes.get(doc.payment_mode, doc.payment_mode)


def _context(doc: ApplicationDocument, rules: Rules) -> dict[str, object]:
    labels = labels_for(doc.language)
    exempt = doc.bpl and rules.act.bpl_fee_exempt.applies
    amount = labels.fee_amount.format(rupees=rules.local.application_fee.rupees)
    return {
        "doc": doc,
        "lang": doc.language,
        "l": labels,
        "run": user_text(doc.language),
        "fee_text": labels.fee_nil if exempt else amount,
        "show_certificate_note": exempt and rules.local.bpl_certificate_required.applies,
        "payment_text": None if exempt else _payment_text(doc, labels),
        "date_text": date_text(doc.prepared_on, labels.months),
        "font_faces": font_faces(),
    }


def render_application_html(doc: ApplicationDocument) -> str:
    rules = load_rules(doc.jurisdiction)
    template = environment().get_template(TEMPLATE_NAME)
    return template.render(_context(doc, rules))


def render_application_pdf(doc: ApplicationDocument) -> bytes:
    return html_to_pdf(render_application_html(doc))
