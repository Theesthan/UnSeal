"""First appeal PDF renderer (FR-10): Jinja2 builds the HTML, WeasyPrint turns it into a PDF.

`render_appeal_html` is pure and runs anywhere. `render_appeal_pdf` needs WeasyPrint's system
libraries (Pango and HarfBuzz shape Tamil and Devanagari), imported only inside that step.

No model writes this letter: the facts come from the case record, the grounds and the relief are
fixed sentences per language, and the section numbers come from `load_rules(doc.jurisdiction)`,
never from a literal (golden rule 1). The page has no fee line, image, emblem or seal and nothing
that claims official status; every page ends with the "Prepared with UnSeal. Not legal advice."
footer.
"""

import re
from collections.abc import Callable
from datetime import date

from markupsafe import Markup

from unseal.pdf.appeal_labels import AppealLabels, appeal_labels_for
from unseal.pdf.common import date_text, environment, font_faces, html_to_pdf, user_text
from unseal.pdf.models import AppealDocument
from unseal.rules.engine import Rules, load_rules

TEMPLATE_NAME = "appeal.html.j2"

# "RTI Act 2005, s. <number>(<sub>)..." followed by the end, a space or a comma. The section is
# taken from the rule's basis so the letter cites exactly what rules/data/rti_act.json says.
_RTI_SECTION = re.compile(r"^RTI Act 2005, s\. (\d+(?:\([0-9a-z]+\))+)(?=$|[\s,])")


def section_number(basis: str) -> str:
    """The RTI Act section a rule rests on, as printed in the letter (the part after "s. ")."""
    match = _RTI_SECTION.match(basis)
    if match is None:
        raise ValueError(f"no RTI Act section in the rule basis {basis!r}")
    return match.group(1)


def _day_markup(labels: AppealLabels) -> Callable[[date], Markup]:
    """A date written out in the document language, machine-readable in <time datetime>."""

    def day(value: date) -> Markup:
        return Markup('<time datetime="{}">{}</time>').format(
            value.isoformat(), date_text(value, labels.months)
        )

    return day


def _context(doc: AppealDocument, rules: Rules) -> dict[str, object]:
    labels = appeal_labels_for(doc.language)
    deemed_refusal = section_number(rules.act.deemed_refusal.basis)
    return {
        "doc": doc,
        "lang": doc.language,
        "l": labels,
        "run": user_text(doc.language),
        "day": _day_markup(labels),
        "title": labels.title.format(section=section_number(rules.act.first_appeal.basis)),
        "grounds": [labels.grounds[code].format(section=deemed_refusal) for code in doc.grounds],
        "date_text": date_text(doc.prepared_on, labels.months),
        "font_faces": font_faces(),
    }


def render_appeal_html(doc: AppealDocument) -> str:
    rules = load_rules(doc.jurisdiction)
    template = environment().get_template(TEMPLATE_NAME)
    return template.render(_context(doc, rules))


def render_appeal_pdf(doc: AppealDocument) -> bytes:
    return html_to_pdf(render_appeal_html(doc))
