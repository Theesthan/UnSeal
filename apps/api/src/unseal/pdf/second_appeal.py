"""Second appeal PDF renderer (FR-12, the appeal to the Commission): Jinja2 builds the HTML,
WeasyPrint the PDF.

The format comes from `load_rules(doc.jurisdiction).local.second_appeal_format`: the CIC rule 8
Appendix (11 items) or the TNSIC form. Its list of copies to enclose comes from there too, less
the copies this case cannot have. No model writes this letter: the facts are fixed sentences over
the case's dates, the grounds are fixed sentences or tick boxes, and `details` and
`delay_reason` are the appellant's own words. Every section number comes from a rule's basis
through `section_number` (golden rule 1). No fee line, emblem or seal; every page carries the
"Prepared with UnSeal. Not legal advice." footer.
"""

from collections.abc import Callable, Mapping, Sequence
from datetime import date

from markupsafe import Markup, escape

from unseal.pdf.appeal import section_number
from unseal.pdf.common import date_text, environment, font_faces, html_to_pdf, user_text
from unseal.pdf.models import SecondAppealDocument, SecondGround
from unseal.pdf.second_appeal_labels import SecondAppealLabels, fill, second_appeal_labels
from unseal.rules.engine import Enclosure, Rules, load_rules

TEMPLATES = {
    "cic_rule_8": "second_appeal_cic.html.j2",
    "tnsic_form": "second_appeal_tnsic.html.j2",
}
TNSIC_REASONS = ("not_furnished", "not_satisfactory", "partial", "improper")

# Needs human review: which of the TNSIC form's four reason boxes ("Reply not furnished by the
# PIO/First Appellate Authority", "Reply not satisfactory", "Partial reply", "Improper reply")
# each UnSeal ground ticks. A reviewer may prefer, for example, "Improper reply" for a fee demand.
TNSIC_REASON_BY_GROUND: dict[SecondGround, str] = {
    "no_reply": "not_furnished",
    "no_decision": "not_furnished",
    "refused": "not_satisfactory",
    "fee_demanded": "not_satisfactory",
    "incomplete": "partial",
    "incorrect": "improper",
}


def _transferred(doc: SecondAppealDocument) -> bool:
    return bool((doc.transferred_to or "").strip())


def enclosures_for(doc: SecondAppealDocument, enclosures: Sequence[Enclosure]) -> list[Enclosure]:
    """The rules' copies to enclose, in their order, less those this case cannot have."""
    missing: set[Enclosure] = set()
    if doc.reply_received_on is None:
        missing.add("pio_reply")
    if doc.faa_decision_received_on is None:
        missing.add("faa_order")
    if not _transferred(doc):
        missing.add("transfer_letter")
    return [code for code in enclosures if code not in missing]


def _sections(rules: Rules) -> dict[str, str]:
    act = rules.act
    return {
        # The request section: the languages rule is the one rule that rests on it.
        "request": section_number(act.languages.basis),
        "transfer": section_number(act.transfer.basis),
        "deemed_refusal": section_number(act.deemed_refusal.basis),
        "first_appeal": section_number(act.first_appeal.basis),
        "faa_decision": section_number(act.faa_decision.basis),
        "second_appeal": section_number(act.second_appeal.basis),
    }


def _sentence(template: str, **values: object) -> Markup:
    """A fixed sentence with dates, names or blanks put in; values that are not Markup escape."""
    return escape(template).format(**values)


def _day_markup(labels: SecondAppealLabels) -> Callable[[date], Markup]:
    def day(value: date) -> Markup:
        return Markup('<time datetime="{}">{}</time>').format(
            value.isoformat(), date_text(value, labels.months)
        )

    return day


def _facts(
    doc: SecondAppealDocument,
    t: Mapping[str, str],
    day: Callable[[date], Markup],
    received: Markup,
    run: Callable[[str], Markup],
) -> list[Markup]:
    """The CIC item 7 chronology, one fixed sentence per step the case has."""
    facts = [_sentence(t["facts_filed"], filed_on=day(doc.filed_on), received_on=received)]
    if _transferred(doc):
        facts.append(_sentence(t["facts_transfer"], transferred_to=run(doc.transferred_to or "")))
    if doc.reply_received_on:
        facts.append(
            _sentence(
                t["facts_reply"], due_on=day(doc.reply_due_on), reply_on=day(doc.reply_received_on)
            )
        )
    else:
        facts.append(_sentence(t["facts_no_reply"], due_on=day(doc.reply_due_on)))
    facts.append(_sentence(t["facts_appeal"], appeal_on=day(doc.appeal_filed_on)))
    if doc.faa_decision_received_on:
        facts.append(_sentence(t["facts_order"], order_on=day(doc.faa_decision_received_on)))
    else:
        facts.append(Markup(escape(t["facts_no_order"])))
    return facts


def _tnsic(
    doc: SecondAppealDocument, t: Mapping[str, str], run: Callable[[str], Markup]
) -> dict[str, object]:
    """The TNSIC form's tick boxes and verification. Part II (the first appeal) ticks "not
    furnished" only when the PIO never replied, and leaves the rest to the appellant; part III
    (the second appeal) ticks the boxes the grounds map to."""
    chosen = {TNSIC_REASON_BY_GROUND[ground] for ground in doc.grounds}
    shared = [t["r_not_satisfactory"], t["r_partial"], t["r_improper"]]
    first_labels = [t["r1_not_furnished"], *shared]
    second_labels = [t["r3_not_furnished"], *shared]
    return {
        "first_reasons": [
            (label, code == "not_furnished" and doc.reply_received_on is None)
            for label, code in zip(first_labels, TNSIC_REASONS, strict=True)
        ],
        "second_reasons": [
            (label, code in chosen)
            for label, code in zip(second_labels, TNSIC_REASONS, strict=True)
        ],
        "declaration1": _sentence(
            t["declaration1"],
            name=run(doc.appellant_name),
            blank=Markup('<span class="blank"></span>'),
        ),
    }


def _cic(
    doc: SecondAppealDocument,
    t: Mapping[str, str],
    day: Callable[[date], Markup],
    received: Markup,
    run: Callable[[str], Markup],
) -> dict[str, object]:
    return {
        "facts": _facts(doc, t, day, received, run),
        "declaration": _sentence(t["declaration"], name=run(doc.appellant_name)),
    }


def _context(doc: SecondAppealDocument, rules: Rules) -> dict[str, object]:
    form = rules.local.second_appeal_format
    labels = second_appeal_labels(form.format, doc.language)
    sections = _sections(rules)
    t = {key: fill(value, sections) for key, value in labels.text.items()}
    day = _day_markup(labels)
    run = user_text(doc.language)
    received = day(doc.received_on)
    if doc.received_estimated:
        received = received + Markup(" ({})").format(t["estimated"])
    codes = enclosures_for(doc, form.enclosures)
    by_format = (
        _cic(doc, t, day, received, run) if form.format == "cic_rule_8" else _tnsic(doc, t, run)
    )
    return {
        "doc": doc,
        "lang": doc.language,
        "l": labels,
        "t": t,
        "sign": labels.sign,
        "run": run,
        "day": day,
        # A dated fixed phrase, for example dated("received_on_date", day): "Received on <day>".
        "dated": lambda key, value: _sentence(t[key], date=day(value)),
        "title": t["title"],
        "received": received,
        "filing_mode": labels.filing_modes[doc.filing_mode],
        "phone": (doc.appellant_phone or "").strip(),
        "transferred": _transferred(doc),
        "details": doc.details.strip(),
        "delay_reason": doc.delay_reason.strip(),
        "grounds": [fill(labels.grounds[g], sections) for g in doc.grounds],
        "codes": codes,
        "enclosures": [fill(labels.enclosures[code], sections) for code in codes],
        "date_text": date_text(doc.prepared_on, labels.months),
        "font_faces": font_faces(),
        **by_format,
    }


def render_second_appeal_html(doc: SecondAppealDocument) -> str:
    rules = load_rules(doc.jurisdiction)
    template = environment().get_template(TEMPLATES[rules.local.second_appeal_format.format])
    return template.render(_context(doc, rules))


def render_second_appeal_pdf(doc: SecondAppealDocument) -> bytes:
    return html_to_pdf(render_second_appeal_html(doc))
